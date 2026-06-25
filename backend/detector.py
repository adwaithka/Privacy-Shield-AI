"""Hybrid detection engine for Privacy Shield AI."""

from __future__ import annotations

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_anonymizer import AnonymizerEngine
import spacy

from recognizers import (
    AadhaarRecognizer,
    PANRecognizer,
    PassportRecognizer,
    IFSCRecognizer,
    IndianPhoneRecognizer,
    BankAccountRecognizer,
    EmployeeIDRecognizer,
)
from rules import extract_rule_based_entities


PRESIDIO_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "URL",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "DATE_TIME",
]

PATTERN_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "AADHAAR",
    "PAN",
    "PASSPORT",
    "IFSC",
    "BANK_ACCOUNT",
    "EMPLOYEE_ID",
]

SPACY_NER_TYPES = {"PERSON", "ORGANIZATION", "LOCATION", "NRP"}
ALL_RULE_TYPES = {
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "ADDRESS",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "DATE_TIME",
    "EMPLOYEE_ID",
}

ENTITY_THRESHOLDS = {
    "PERSON": 0.65,
    "ORGANIZATION": 0.70,
    "LOCATION": 0.70,
    "EMAIL_ADDRESS": 0.98,
    "PHONE_NUMBER": 0.90,
    "AADHAAR": 0.98,
    "PAN": 0.99,
    "PASSPORT": 0.90,
    "IFSC": 0.90,
    "BANK_ACCOUNT": 0.95,
    "EMPLOYEE_ID": 0.95,
    "DATE_TIME": 0.80,
    "URL": 0.80,
    "CREDIT_CARD": 0.95,
}

OVERLAP_PRIORITY = {
    "EMAIL_ADDRESS": 100,
    "URL": 90,
    "BANK_ACCOUNT": 80,
    "AADHAAR": 70,
    "ADDRESS": 60,
    "LOCATION": 50,
    "PASSPORT": 45,
    "PERSON": 40,
    "NRP": 30,
}

SPACY_LABEL_MAP = {
    "PERSON": "PERSON",
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "NORP": "NRP",
    "NRP": "NRP",
}

SPACY_ENTITY_SCORES = {
    "PERSON": 0.88,
    "ORGANIZATION": 0.84,
    "LOCATION": 0.84,
    "NRP": 0.80,
}

SPACY_MODEL = "en_core_web_sm"
SPACY_LABEL_STOPWORDS = {
    "aadhaar",
    "address",
    "alternate contact",
    "bank account",
    "date",
    "email",
    "employee id",
    "emergency contact",
    "location",
    "mobile",
    "name",
    "organization",
    "organisation",
    "phone",
    "secondary email",
    "url",
}

ALL_PRESIDIO_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "AADHAAR",
    "PAN",
    "PASSPORT",
    "IFSC",
    "BANK_ACCOUNT",
    "EMPLOYEE_ID",
    "URL",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "DATE_TIME",
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "NRP",
]

CATEGORY_MAP = {
    "name": ["PERSON"],
    "email": ["EMAIL_ADDRESS"],
    "phone": ["PHONE_NUMBER"],
    "address": ["ADDRESS", "LOCATION"],
    "aadhaar": ["AADHAAR"],
    "pan": ["PAN"],
    "passport": ["PASSPORT"],
    "ifsc": ["IFSC"],
    "bank": ["BANK_ACCOUNT"],
    "employee_id": ["EMPLOYEE_ID"],
    "organization": ["ORGANIZATION"],
    "date": ["DATE_TIME"],
    "url": ["URL"],
    "ip": ["IP_ADDRESS"],
    "credit_card": ["CREDIT_CARD"],
    "qr_code": ["QR_CODE"],
}

AVAILABLE_TARGETS = [
    {"key": "all", "label": "Everything (full auto-redact)"},
    {"key": "name", "label": "Names"},
    {"key": "email", "label": "Email addresses"},
    {"key": "phone", "label": "Phone numbers"},
    {"key": "address", "label": "Addresses & locations"},
    {"key": "aadhaar", "label": "Aadhaar numbers"},
    {"key": "pan", "label": "PAN numbers"},
    {"key": "passport", "label": "Passport numbers"},
    {"key": "ifsc", "label": "IFSC codes"},
    {"key": "bank", "label": "Bank account numbers"},
    {"key": "employee_id", "label": "Employee IDs"},
    {"key": "organization", "label": "Organizations"},
    {"key": "date", "label": "Dates & times"},
    {"key": "url", "label": "URLs"},
    {"key": "credit_card", "label": "Credit card numbers"},
    {"key": "qr_code", "label": "QR codes"},
]


class StrictEmailRecognizer(PatternRecognizer):
    """High-confidence email matcher used independently of Presidio built-ins."""

    PATTERNS = [
        Pattern(
            "email_strict",
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            0.99,
        )
    ]

    def __init__(self) -> None:
        super().__init__(supported_entity="EMAIL_ADDRESS", patterns=self.PATTERNS)


presidio_registry = RecognizerRegistry()
presidio_registry.load_predefined_recognizers()
for recognizer_name in ("SpacyRecognizer", "TransformersRecognizer"):
    try:
        presidio_registry.remove_recognizer(recognizer_name)
    except Exception:
        pass

pattern_registry = RecognizerRegistry()
pattern_registry.add_recognizer(StrictEmailRecognizer())
pattern_registry.add_recognizer(AadhaarRecognizer())
pattern_registry.add_recognizer(PANRecognizer())
pattern_registry.add_recognizer(PassportRecognizer())
pattern_registry.add_recognizer(IFSCRecognizer())
pattern_registry.add_recognizer(IndianPhoneRecognizer())
pattern_registry.add_recognizer(BankAccountRecognizer())
pattern_registry.add_recognizer(EmployeeIDRecognizer())

presidio_analyzer = AnalyzerEngine(registry=presidio_registry, supported_languages=["en"])
pattern_analyzer = AnalyzerEngine(registry=pattern_registry, supported_languages=["en"])
anonymizer = AnonymizerEngine()
_spacy_nlp = None


def get_detector_info() -> dict:
    """Return metadata about the active detection stack."""
    return {
        "spacy_model": _get_spacy_model_name(),
        "presidio_entities": ALL_PRESIDIO_ENTITIES,
        "spacy_ner_entities": sorted(SPACY_NER_TYPES),
        "rule_entities": sorted(ALL_RULE_TYPES),
    }


def _get_spacy_nlp():
    """Return a singleton native spaCy pipeline for direct NER."""
    global _spacy_nlp
    if _spacy_nlp is None:
        _spacy_nlp = spacy.load(SPACY_MODEL)
    return _spacy_nlp


def _get_spacy_model_name() -> str:
    """Return the configured native spaCy model name."""
    try:
        return _get_spacy_nlp().meta.get("name", SPACY_MODEL)
    except Exception:
        return SPACY_MODEL


def _resolve_target_entities(targets, use_all: bool) -> tuple[set[str], set[str]]:
    """Map UI targets to detector entity sets and rules.py type filters."""
    if use_all:
        return set(ALL_PRESIDIO_ENTITIES), set(ALL_RULE_TYPES)

    wanted_entities = set()
    rule_types_wanted = set()
    for target in targets:
        for entity_type in CATEGORY_MAP.get(target.lower(), []):
            wanted_entities.add(entity_type)
            if entity_type in ALL_RULE_TYPES:
                rule_types_wanted.add(entity_type)
    return wanted_entities, rule_types_wanted


def _presidio_results(text: str, wanted_entities: set[str]) -> list[RecognizerResult]:
    """Run Presidio only for built-in non-spaCy entities."""
    entities = sorted(wanted_entities & set(PRESIDIO_ENTITIES))
    if not entities:
        return []
    return [
        _normalize_result_span(text, result)
        for result in presidio_analyzer.analyze(text=text, language="en", entities=entities)
        if text[result.start:result.end].strip()
    ]


def _spacy_results(text: str, wanted_entities: set[str]) -> list[RecognizerResult]:
    """Run native spaCy NER and convert selected labels to RecognizerResult."""
    wanted = wanted_entities & SPACY_NER_TYPES
    if not wanted:
        return []

    results = []
    for ent in _get_spacy_nlp()(text).ents:
        entity_type = SPACY_LABEL_MAP.get(ent.label_)
        if entity_type not in wanted:
            continue
        snippet = text[ent.start_char:ent.end_char].strip()
        if not snippet or snippet.lower().rstrip(":") in SPACY_LABEL_STOPWORDS:
            continue
        results.append(
            RecognizerResult(
                entity_type=entity_type,
                start=ent.start_char,
                end=ent.end_char,
                score=SPACY_ENTITY_SCORES.get(entity_type, 0.80),
            )
        )
    return results


def _pattern_results(text: str, wanted_entities: set[str]) -> list[RecognizerResult]:
    """Run custom PatternRecognizer instances independently of Presidio built-ins."""
    entities = sorted(wanted_entities & set(PATTERN_ENTITIES))
    if not entities:
        return []
    return [
        _normalize_result_span(text, result)
        for result in pattern_analyzer.analyze(text=text, language="en", entities=entities)
        if text[result.start:result.end].strip()
    ]


def _normalize_result_span(text: str, result: RecognizerResult) -> RecognizerResult:
    """Trim known over-wide recognizer spans while preserving entity metadata."""
    if result.entity_type != "EMAIL_ADDRESS":
        return result

    value = text[result.start:result.end]
    at_index = value.find("@")
    slash_index = value.rfind("/", 0, at_index)
    if slash_index == -1:
        return result

    new_start = result.start + slash_index + 1
    return RecognizerResult(
        entity_type=result.entity_type,
        start=new_start,
        end=result.end,
        score=result.score,
        analysis_explanation=result.analysis_explanation,
        recognition_metadata=result.recognition_metadata,
    )


def _rule_results(text: str, wanted_types: set[str], use_all: bool) -> list[RecognizerResult]:
    """Convert rules.py structured extraction matches to RecognizerResult objects."""
    results = []
    used_spans = set()
    for entity in extract_rule_based_entities(text):
        if not (use_all or entity["type"] in wanted_types):
            continue
        entity_text = entity["text"]
        search_from = 0
        while True:
            start = text.find(entity_text, search_from)
            if start == -1:
                break
            key = (entity["type"], start, start + len(entity_text))
            if key not in used_spans:
                used_spans.add(key)
                results.append(
                    RecognizerResult(
                        entity_type=entity["type"],
                        start=start,
                        end=start + len(entity_text),
                        score=1.0,
                    )
                )
            search_from = start + len(entity_text)
    return results


def _merge_results(*result_groups: list[RecognizerResult]) -> list[RecognizerResult]:
    """Combine independent detector outputs into one flat result list."""
    merged = []
    for group in result_groups:
        merged.extend(group)
    return merged


def _passes_threshold(result: RecognizerResult) -> bool:
    """Return whether a result meets the configured entity confidence threshold."""
    return result.score >= ENTITY_THRESHOLDS.get(result.entity_type, 0.0)


def _remove_duplicates(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Remove duplicate entity spans, keeping the highest confidence duplicate."""
    best = {}
    for result in results:
        if not _passes_threshold(result):
            continue
        key = (result.entity_type, result.start, result.end)
        existing = best.get(key)
        if existing is None or result.score > existing.score:
            best[key] = result
    return list(best.values())


def _overlaps(left: RecognizerResult, right: RecognizerResult) -> bool:
    """Return True when two result spans share at least one character."""
    return left.start < right.end and right.start < left.end


def _overlap_rank(result: RecognizerResult) -> tuple[int, int, float]:
    """Rank an entity for overlap resolution by priority, length, then score."""
    return (
        OVERLAP_PRIORITY.get(result.entity_type, 0),
        result.end - result.start,
        result.score,
    )


def _remove_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Resolve overlapping spans with entity priority, span length, and confidence."""
    kept: list[RecognizerResult] = []
    for result in sorted(results, key=lambda item: (item.start, item.end)):
        replacement_index = None
        should_keep = True
        for idx, existing in enumerate(kept):
            if not _overlaps(existing, result):
                continue
            if _overlap_rank(result) > _overlap_rank(existing):
                replacement_index = idx
            else:
                should_keep = False
            break

        if replacement_index is not None:
            kept[replacement_index] = result
        elif should_keep:
            kept.append(result)

    return _sort_entities(kept)


def _sort_entities(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Sort entities in document order with longer same-start spans first."""
    return sorted(results, key=lambda item: (item.start, -(item.end - item.start), item.entity_type))


def analyze_text(text, targets=None):
    """Analyze text with Presidio, native spaCy, custom patterns, and rules."""
    if not text or not text.strip():
        return []

    use_all = (not targets) or ("all" in targets)
    wanted_entities, rule_types_wanted = _resolve_target_entities(targets, use_all)
    merged = _merge_results(
        _presidio_results(text, wanted_entities),
        _spacy_results(text, wanted_entities),
        _pattern_results(text, wanted_entities),
        _rule_results(text, rule_types_wanted, use_all),
    )
    return _remove_overlaps(_remove_duplicates(merged))


def anonymize_text(text, targets=None):
    """Return anonymized text after hybrid entity detection."""
    if not text or not text.strip():
        return text
    results = analyze_text(text, targets)
    if not results:
        return text
    return anonymizer.anonymize(text=text, analyzer_results=results).text
