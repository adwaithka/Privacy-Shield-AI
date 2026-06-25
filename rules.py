"""
rules.py v3.6

Fixes:
  - Location regex: removed ^ anchor so it matches even when OCR noise
    prefixes the line (e.g. "i @ Location: Bengaluru, India")
  - Standalone name detection: finds 2-word Title Case lines on cards
    that don't use a "Name :" label format
  - Phone: handles +91 prefix and spaced formats like "+91 98765 43210"
  - Date of Joining treated same as Date of Birth → DATE_TIME entity
  - Department captured as ORGANIZATION fallback
"""
import re


def extract_rule_based_entities(text):
    entities = []
    seen = set()

    def add(etype, value):
        v = value.strip()
        if not v or v in seen:
            return
        seen.add(v)
        entities.append({"type": etype, "text": v})

    def add_address(value):
        """Bypass dedup for address tokens — redactor deduplicates bboxes."""
        v = value.strip()
        if not v:
            return
        entities.append({"type": "ADDRESS", "text": v})

    # ── Name (labelled) ───────────────────────────────────────────────────────
    m = re.search(
        r"(?:Full\s+)?Name\s*:\s*([A-Za-z][A-Za-z .'-]{1,50}?)(?=\s*\n|\s*$)",
        text, re.IGNORECASE
    )
    if m:
        full_name = m.group(1).strip()
        add("PERSON", full_name)
        # Also register each word so partial OCR reads (e.g. "Sharms" for "Sharma") still match
        for word in full_name.split():
            if len(word) >= 3:
                add("PERSON", word)

    # ── Name (unlabelled — standalone 2-3 word Title Case line) ───────────────
    # Catches cards like "Rahul Sharma\nSoftware Engineer" where there's no label
    if not any(e["type"] == "PERSON" for e in entities):
        for line in text.splitlines():
            line = line.strip()
            # Must be 2-3 words, all starting with capital, no digits/symbols
            if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$', line):
                # Skip common non-name title lines
                skip = {"Software Engineer", "Authorized Signatory", "Date Joining",
                        "Employee Information", "Human Resources", "General Manager",
                        "Redacted Image", "Id Card", "Employee Card"}
                if line not in skip and not any(w in line for w in
                        ["Engineer", "Manager", "Director", "Officer", "Signatory",
                         "Solutions", "Department", "Information", "Redacted", "Image",
                         "Card", "Preview"]):
                    add("PERSON", line)
                    # Also register each word of the name separately
                    for word in line.split():
                        if len(word) >= 3:
                            add("PERSON", word)
                    break  # take the first match only

    # ── Email ─────────────────────────────────────────────────────────────────
    for m in re.finditer(
        r"(?:Secondary|Alternate|Work)?\s*Email\s*:\s*"
        r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
        text, re.IGNORECASE
    ):
        add("EMAIL_ADDRESS", m.group(1))

    # Also catch any bare email not preceded by a label
    for m in re.finditer(
        r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b", text
    ):
        add("EMAIL_ADDRESS", m.group(1))

    # ── Phone ─────────────────────────────────────────────────────────────────
    for pattern in [
        # Labelled phone with optional +91 prefix and spaces
        r"(?:Phone|Mobile|Tel(?:ephone)?)\s*:\s*(\+?[\d][\d\s\-]{6,16})",
        # Alternate/Emergency contact
        r"(?:Alternate|Emergency|Secondary)\s+Contact\s*:\s*(\+?[\d][\d\s\-]{6,16})",
    ]:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            val = m.group(1).strip().rstrip(".,;")
            add("PHONE_NUMBER", val)

    # ── Dates (Birth, Joining, Issue, Expiry) ─────────────────────────────────
    for pattern in [
        r"Date\s+of\s+(?:Birth|Joining|Issue|Expiry)\s*:\s*([^\n]{4,20})",
        r"(?:DOB|D\.O\.B\.?)\s*:\s*([^\n]{4,20})",
        r"Valid\s+(?:Until|Till|Upto)\s*:\s*([^\n]{4,20})",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            add("DATE_TIME", m.group(1).strip())

    # ── Organisation / Department ─────────────────────────────────────────────
    for pat in [
        r"(?:Organization|Organisation|Company|Employer)\s*:\s*([^\n]+)",
        r"Department\s*:\s*([^\n]+)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            add("ORGANIZATION", m.group(1).strip())

    # ── Location — NO ^ anchor so noise prefix doesn't block match ────────────
    m = re.search(r"Location\s*:\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        loc = m.group(1).strip()
        add("LOCATION", loc)
        # Also register as ADDRESS so the image redactor blacks it out
        add_address(loc)

    # ── Address (multi-line) ──────────────────────────────────────────────────
    addr_m = re.search(
        r"Address\s*:\s*(.*?)(?=\n[A-Za-z][A-Za-z ]{2,}\s*:\s|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    if addr_m:
        raw = addr_m.group(1)
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if lines:
            add_address(" ".join(lines))        # full joined address
            for ln in lines:
                add_address(ln)                 # each line individually
                pm = re.search(r"\b(\d{6})\b", ln)
                if pm:
                    add_address(pm.group(1))    # standalone pincode


    # ── Company name from logo/header (not labelled) ──────────────────────────
    # Strategy: find "SOLUTIONS" line, then look at same line AND line above
    # for candidate company name words (>= 5 chars, not generic terms)
    SKIP_WORDS = {"employee","card","information","solutions","authorized",
                  "signatory","department","engineering","redacted","image",
                  "preview","integrate","innovate","elevate"}
    lines_list = text.splitlines()
    for i, line in enumerate(lines_list):
        stripped = line.strip()
        if re.search(r"\bSolutions?\b", stripped, re.IGNORECASE):
            # Check line above for company name words
            candidates = []
            if i > 0:
                prev_words = re.findall(r"[A-Za-z][A-Za-z0-9]+", lines_list[i-1])
                for w in prev_words:
                    if len(w) >= 4 and w.lower() not in SKIP_WORDS:
                        candidates.append(w)
            # Also check same line (before "Solutions")
            same_m = re.search(r"([A-Za-z][A-Za-z0-9]+)\s+Solutions?", stripped, re.IGNORECASE)
            if same_m and same_m.group(1).lower() not in SKIP_WORDS:
                candidates.append(same_m.group(1))

            # Also register "SOLUTIONS" itself
            add("ORGANIZATION", "SOLUTIONS")
            for cand in candidates:
                add("ORGANIZATION", cand)
                # Also register each word token separately for fuzzy matching
                add("PERSON", cand)  # treat as PERSON too so name-mode masks it


    # ── Employee ID ───────────────────────────────────────────────────────────
    m = re.search(
        r"Employee\s*(?:ID|Id|No\.?)\s*:\s*([A-Z0-9\-]{4,20})",
        text, re.IGNORECASE
    )
    if m:
        add("EMPLOYEE_ID", m.group(1))

    return entities