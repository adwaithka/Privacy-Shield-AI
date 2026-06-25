"""
redactor.py v3.3

Rewrite of image redaction using direct word-bbox lookup.

Strategy:
  1. Run Tesseract once → get all (word, bbox) pairs with conf > 40
  2. Build a word-level lookup: normalized_word → list of bboxes
  3. For each entity, split into meaningful tokens and black-box every
     matching word bbox on the image
  4. Face blur with OpenCV (unchanged)

Why word-level is better than char-offset mapping:
  - OCR output has noise chars and artifacts between real words
  - Word bboxes are stable and accurate even when chars aren't
  - Multi-line values (address, bank account) are naturally handled
    because we look up each token independently

Special handling:
  - Numeric sequences (bank account, phone) are tokenised by splitting
    on spaces so "5010 1234 5678 90" → 4 separate lookups
  - Email is looked up as-is AND split at @ and . for partial matches
  - Short tokens (≤ 2 chars) skipped to avoid over-redacting
"""

import io
import re
import cv2
import numpy as np
import fitz
import pytesseract

from PIL import Image, ImageDraw, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

HAAR_FACE    = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
HAAR_PROFILE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
DNN_FACE_PROTO = cv2.data.haarcascades + "deploy.prototxt"
DNN_FACE_MODEL = cv2.data.haarcascades + "res10_300x300_ssd_iter_140000.caffemodel"

MIN_CONF = 20   # minimum Tesseract confidence to include a word
PDF_OCR_DPI = 250
REDACTION_PAD_PX = 2


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(text):
    return text.encode("latin-1", errors="replace").decode("latin-1")

def _norm(s):
    """Lowercase, strip punctuation for matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ── Face blur ─────────────────────────────────────────────────────────────────

def _blur_faces(pil_img):
    arr  = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    faces = set()

    faces.update(_detect_dnn_faces(arr))

    for scale in [1.05, 1.1, 1.15]:
        det = HAAR_FACE.detectMultiScale(gray, scaleFactor=scale, minNeighbors=4, minSize=(30, 30))
        if len(det):
            for (x, y, w, h) in det:
                faces.add((int(x), int(y), int(w), int(h)))

    det_p = HAAR_PROFILE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
    if len(det_p):
        for (x, y, w, h) in det_p:
            faces.add((int(x), int(y), int(w), int(h)))

    real_faces = [face for face in faces if _looks_like_real_face(arr, face)]

    img_out = pil_img.convert("RGB")
    for (x, y, w, h) in real_faces:
        pad_x, pad_y = int(w * 0.15), int(h * 0.15)
        x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
        x2, y2 = min(img_out.width, x + w + pad_x), min(img_out.height, y + h + pad_y)
        region  = img_out.crop((x1, y1, x2, y2))
        tiny    = region.resize((8, 8), Image.NEAREST)
        blurred = tiny.resize(region.size, Image.NEAREST).filter(ImageFilter.GaussianBlur(radius=10))
        img_out.paste(blurred, (x1, y1))

    print(f"[redactor] Faces blurred: {len(real_faces)}")
    return img_out, len(real_faces)


def _detect_dnn_faces(arr):
    """Use OpenCV's DNN face detector when its model files are available."""
    import os

    if not (os.path.exists(DNN_FACE_PROTO) and os.path.exists(DNN_FACE_MODEL)):
        return []

    try:
        net = cv2.dnn.readNetFromCaffe(DNN_FACE_PROTO, DNN_FACE_MODEL)
        h, w = arr.shape[:2]
        blob = cv2.dnn.blobFromImage(arr, 1.0, (300, 300), (104, 177, 123))
        net.setInput(blob)
        detections = net.forward()
    except Exception:
        return []

    faces = []
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        if confidence < 0.65:
            continue
        x1, y1, x2, y2 = (detections[0, 0, i, 3:7] * np.array([w, h, w, h])).astype("int")
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 > x1 and y2 > y1:
            faces.append((x1, y1, x2 - x1, y2 - y1))
    return faces


def _looks_like_real_face(arr, face):
    """Reject flat cartoon-like detections with little texture or skin-tone evidence."""
    x, y, w, h = face
    crop = arr[y:y + h, x:x + w]
    if crop.size == 0:
        return False

    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    if float(gray.std()) < 18:
        return False

    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    lower = np.array([0, 20, 40], dtype=np.uint8)
    upper = np.array([35, 220, 255], dtype=np.uint8)
    skin_mask = cv2.inRange(hsv, lower, upper)
    skin_ratio = float(np.count_nonzero(skin_mask)) / skin_mask.size
    return skin_ratio >= 0.12




# ── QR code detection & blacking ─────────────────────────────────────────────

def _redact_qr_codes(pil_img):
    """
    Detect all QR codes in a PIL image using OpenCV and draw solid black
    rectangles over each one. Returns (modified_img, count_found).
    """
    import cv2
    arr  = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    qr_detector = cv2.QRCodeDetector()
    found_count = 0

    # detectMulti returns (retval, decoded_list, points_array, straight_qrcode_list)
    try:
        retval, decoded_list, points_array, _ = qr_detector.detectAndDecodeMulti(gray)
    except Exception:
        retval = False
        points_array = None

    draw = ImageDraw.Draw(pil_img)
    if retval and points_array is not None:
        for pts in points_array:
            if pts is None or len(pts) == 0:
                continue
            # pts is shape (N,2) — get bounding box
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            pad = 10
            x1, y1 = int(min(xs)) - pad, int(min(ys)) - pad
            x2, y2 = int(max(xs)) + pad, int(max(ys)) + pad
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(pil_img.width, x2), min(pil_img.height, y2)
            draw.rectangle([x1, y1, x2, y2], fill="black")
            found_count += 1
            print(f"[redactor] QR code blacked out at ({x1},{y1},{x2},{y2})")

    if found_count == 0:
        print("[redactor] No QR codes detected")

    return pil_img, found_count

# ── OCR word-bbox index ───────────────────────────────────────────────────────

def _build_word_index(pil_img):
    """
    Run Tesseract and return:
      word_index: dict mapping normalized_word → list of (x1,y1,x2,y2) bboxes
      raw_words:  list of (original_word, bbox) for logging
    """
    data = pytesseract.image_to_data(
        pil_img,
        lang="eng",
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )

    word_index = {}
    raw_words  = []

    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            continue
        if conf < MIN_CONF:
            continue

        bbox = (
            data["left"][i],
            data["top"][i],
            data["left"][i] + data["width"][i],
            data["top"][i]  + data["height"][i],
        )
        raw_words.append((word, bbox))

        key = _norm(word)
        if key:
            word_index.setdefault(key, []).append(bbox)

    return word_index, raw_words


def _tokens_for_entity(entity_text):
    """
    Break entity text into lookup tokens.
    Each token must be ≥ 3 chars (normalized) to avoid false positives.
    """
    tokens = set()
    raw_text = entity_text.strip()

    # Full entity as one token
    full_norm = _norm(raw_text)
    if len(full_norm) >= 2:
        tokens.add(full_norm)

    # Split on whitespace and punctuation
    parts = re.split(r"[\s,.\-@/\\]+", raw_text)
    for p in parts:
        pn = _norm(p)
        if len(pn) >= 2:
            tokens.add(pn)

    # For emails: also add username and domain parts
    if "@" in raw_text:
        user, _, domain = raw_text.partition("@")
        for sub in [user, domain]:
            sn = _norm(sub)
            if len(sn) >= 3:
                tokens.add(sn)
        # also add domain without TLD
        dom_parts = domain.split(".")
        if dom_parts:
            dn = _norm(dom_parts[0])
            if len(dn) >= 3:
                tokens.add(dn)

    return tokens


def _fuzzy_match(tok, key):
    """
    Returns True if tok and key are similar enough to be the same word.
    Handles OCR typos like 'Sharms' vs 'Sharma', 'TechNov' vs 'TechNova'.
    Uses: exact, substring, and character similarity >= 0.80 for len >= 4.
    """
    if tok == key:
        return True
    if len(tok) >= 4 and len(key) >= 3:
        # Substring match
        if tok in key or key in tok:
            return True
        # Similarity: if lengths are within 2 and 80%+ chars match
        if abs(len(tok) - len(key)) <= 2:
            shorter, longer = (tok, key) if len(tok) <= len(key) else (key, tok)
            common = sum(a == b for a, b in zip(shorter, longer))
            ratio  = common / len(longer)
            if ratio >= 0.80:
                return True
    return False


def _find_bboxes(word_index, entity_text):
    """
    Find all word bboxes that correspond to any token of entity_text.
    Uses fuzzy matching to handle OCR typos (Sharms/Sharma, TechNov/TechNova).
    Returns list of (x1,y1,x2,y2).
    """
    tokens  = _tokens_for_entity(entity_text)
    bboxes  = []
    matched = set()

    for tok in tokens:
        for key, key_bboxes in word_index.items():
            if _fuzzy_match(tok, key):
                for bbox in key_bboxes:
                    if bbox not in matched:
                        matched.add(bbox)
                        bboxes.append(bbox)

    return bboxes




def _merge_adjacent_bboxes(bboxes, gap=80):
    """
    Merge bounding boxes that are on the same line and within `gap` pixels
    of each other horizontally. This closes small visible gaps (like a dash
    separator) between adjacent redaction boxes.
    """
    if not bboxes:
        return bboxes
    # Sort by top then left
    sorted_b = sorted(bboxes, key=lambda b: (b[1], b[0]))
    merged = [sorted_b[0]]
    for (x1, y1, x2, y2) in sorted_b[1:]:
        px1, py1, px2, py2 = merged[-1]
        same_line = abs(y1 - py1) < 20 and abs(y2 - py2) < 20
        close_enough = x1 - px2 <= gap
        if same_line and close_enough:
            merged[-1] = (min(px1, x1), min(py1, y1), max(px2, x2), max(py2, y2))
        else:
            merged.append((x1, y1, x2, y2))
    return merged



# ── Signature detection & blacking ───────────────────────────────────────────

def _redact_signatures(pil_img, word_index):
    """
    Detect handwritten signature areas by locating "Authorized Signatory" or
    similar labels and blacking out the region directly above them.
    Also blacks out any text that OCR misreads from the signature area.

    Strategy:
      1. Find "Authorized" or "Signatory" word bboxes
      2. Black out a region spanning from 100px above that label down to the label
      3. Extend horizontally to cover the full signature width
    """
    draw = ImageDraw.Draw(pil_img)
    count = 0

    # Keywords that indicate a signature label below a handwritten signature
    sig_labels = ["authorized", "signatory", "signature", "authorised", "signed"]

    # Find all signature label words
    label_boxes = []
    for key, bboxes in word_index.items():
        if key in sig_labels:
            label_boxes.extend(bboxes)

    if label_boxes:
        # Get the topmost y of any label box
        label_top = min(b[1] for b in label_boxes)
        label_left = min(b[0] for b in label_boxes)
        label_right = max(b[2] for b in label_boxes)

        # Signature sits above the label — redact from 120px above label_top
        # down to the label_top, with 20px horizontal padding
        sig_x1 = max(0, label_left - 20)
        sig_y1 = max(0, label_top - 95)
        sig_x2 = min(pil_img.width,  label_right + 20)
        sig_y2 = label_top - 5  # stop just above the label text

        if sig_x2 > sig_x1 and sig_y2 > sig_y1:
            draw.rectangle([sig_x1, sig_y1, sig_x2, sig_y2], fill="black")
            count += 1
            print(f"[redactor] Signature area blacked out at ({sig_x1},{sig_y1},{sig_x2},{sig_y2})")

    if count == 0:
        print("[redactor] No signature area detected")

    return pil_img, count

# ── Main image redactor ───────────────────────────────────────────────────────

def _redact_image(image_path, entities, mask_face=True, mask_qr=True):
    img = Image.open(image_path).convert("RGB")

    if mask_face:
        img, _ = _blur_faces(img)

    # Detect and black out QR codes if requested
    if mask_qr:
        img, qr_count = _redact_qr_codes(img)

    if not entities:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    print("[redactor] Building OCR word index...")
    try:
        word_index, raw_words = _build_word_index(img)
        print(f"[redactor] {len(raw_words)} words indexed")
    except Exception as e:
        print(f"[redactor] OCR failed: {e}")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    # Redact signature area (above "Authorized Signatory" label)
    img, _ = _redact_signatures(img, word_index)

    draw          = ImageDraw.Draw(img)
    total_boxes   = 0
    PAD           = REDACTION_PAD_PX

    for ent in entities:
        ent_text = (ent.get("text") or "").strip()
        if not ent_text:
            continue

        found = _find_bboxes(word_index, ent_text)
        for (x1, y1, x2, y2) in found:
            draw.rectangle(
                [x1 - PAD, y1 - PAD, x2 + PAD, y2 + PAD],
                fill="black",
            )
            total_boxes += 1

        if found:
            print(f"[redactor]  OK '{ent_text[:40]}' -> {len(found)} box(es)")
        else:
            print(f"[redactor]  MISS '{ent_text[:40]}' -> no match")

    print(f"[redactor] Total redaction boxes drawn: {total_boxes}")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ── Native PDF redaction ───────────────────────────────────────────────────────

def _redact_native_pdf(pdf_path, entities):
    """Redact PDFs using OCR word boxes so labels and whitespace are preserved."""
    doc = fitz.open(pdf_path)
    for page in doc:
        pix = page.get_pixmap(dpi=PDF_OCR_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        word_index, _ = _build_word_index(img)
        scale_x = pix.width / page.rect.width
        scale_y = pix.height / page.rect.height

        for ent in entities:
            ent_text = (ent.get("text") or "").strip()
            if not ent_text:
                continue
            for x1, y1, x2, y2 in _find_bboxes(word_index, ent_text):
                rect = fitz.Rect(
                    max(0, (x1 - REDACTION_PAD_PX) / scale_x),
                    max(0, (y1 - REDACTION_PAD_PX) / scale_y),
                    min(page.rect.width, (x2 + REDACTION_PAD_PX) / scale_x),
                    min(page.rect.height, (y2 + REDACTION_PAD_PX) / scale_y),
                )
                page.add_redact_annot(rect, fill=(0, 0, 0))

        image_mode = getattr(fitz, "PDF_REDACT_IMAGE_PIXELS", 2)
        page.apply_redactions(images=image_mode)
    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True, incremental=False)
    doc.close()
    buf.seek(0)
    return buf.read()


# ── Text → PDF ────────────────────────────────────────────────────────────────

def _build_text_pdf(masked_text, title="Redacted Document"):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    mx, my = 20 * mm, 20 * mm
    lh, x, y = 13, mx, h - my

    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(rl_colors.HexColor("#0c1f3f"))
    c.drawString(x, y, _safe(title[:80]))
    y -= lh * 2

    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(rl_colors.HexColor("#64748b"))
    c.drawString(x, y, "REDACTED BY PRIVACY SHIELD AI  |  PII replaced with <ENTITY_TYPE> placeholders")
    y -= lh * 2

    c.setFont("Courier", 8.5)
    c.setFillColor(rl_colors.black)
    for raw_line in masked_text.splitlines():
        line = _safe(raw_line) if raw_line else ""
        for i in range(0, max(1, len(line)), 100):
            if y < my + lh:
                c.showPage()
                c.setFont("Courier", 8.5)
                c.setFillColor(rl_colors.black)
                y = h - my
            c.drawString(x, y, line[i:i + 100])
            y -= lh

    c.save()
    buf.seek(0)
    return buf.read()


# ── Public entry point ────────────────────────────────────────────────────────

def produce_redacted_file(
    file_path,
    extracted_text,
    masked_text,
    entities,
    results,
    is_image=False,
    original_filename="document",
    mask_face=True,
    mask_qr=True,
):
    if is_image:
        return _redact_image(file_path, entities, mask_face=mask_face, mask_qr=mask_qr)

    lower = file_path.lower()
    if lower.endswith(".pdf"):
        try:
            return _redact_native_pdf(file_path, entities)
        except Exception as e:
            print(f"[redactor] Native PDF redaction failed ({e}), fallback to text PDF")

    return _build_text_pdf(masked_text, title=f"Redacted: {original_filename}")
