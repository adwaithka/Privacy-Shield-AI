"""
spaCy integration for Privacy Shield AI.

Provides a shared Presidio NlpEngine (spaCy-backed) used by AnalyzerEngine,
plus helpers to complement regex / pattern recognizers with NER on free-form text.
"""

from pathlib import Path

from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

CONFIG_PATH = Path(__file__).parent / "spacy_config.yaml"

# spaCy NER label → Privacy Shield entity type
SPACY_LABEL_MAP = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "NORP": "NRP",
}

# Default confidence for direct spaCy NER hits (rules/patterns use 1.0 or pattern scores)
SPACY_NER_SCORE = 0.88

_nlp_engine = None


def create_nlp_engine():
    """Build and load the Presidio spaCy NlpEngine from project config."""
    provider = NlpEngineProvider(conf_file=str(CONFIG_PATH))
    return provider.create_engine()


def get_nlp_engine():
    """Return a singleton NlpEngine shared by Presidio and complement helpers."""
    global _nlp_engine
    if _nlp_engine is None:
        _nlp_engine = create_nlp_engine()
    return _nlp_engine


def get_spacy_model_name() -> str:
    """Return the loaded English spaCy model name, if available."""
    engine = get_nlp_engine()
    if not engine.nlp or "en" not in engine.nlp:
        return "unknown"
    return engine.nlp["en"].meta.get("name", "en")


def spacy_entities_to_results(text, wanted_types, existing_spans=None):
    """
    Run spaCy NER once and return RecognizerResult objects for wanted entity types.

    Used alongside Presidio pattern recognizers and rules.py heuristics so
    free-form names, organizations, and locations are caught when label-based
    regex patterns miss (e.g. OCR noise, unstructured prose).
    """
    if not text or not text.strip() or not wanted_types:
        return []

    wanted = set(wanted_types)
    existing_spans = existing_spans or set()

    engine = get_nlp_engine()
    artifacts = engine.process_text(text, language="en")
    results = []

    scores = artifacts.scores or []
    for idx, ent in enumerate(artifacts.entities):
        entity_type = ent.label_
        if entity_type not in wanted:
            continue

        span_key = (entity_type, ent.start_char, ent.end_char)
        if span_key in existing_spans:
            continue

        snippet = text[ent.start_char:ent.end_char].strip()
        if not snippet or (entity_type == "PERSON" and len(snippet) < 2):
            continue

        score = scores[idx] if idx < len(scores) else SPACY_NER_SCORE
        results.append(
            RecognizerResult(
                entity_type=entity_type,
                start=ent.start_char,
                end=ent.end_char,
                score=score,
            )
        )

    return results


def complement_with_spacy(text, wanted_types, existing_results):
    """
    Add spaCy NER hits that are not already covered by Presidio patterns or rules.
    """
    existing_spans = {(r.entity_type, r.start, r.end) for r in existing_results}
    ner_types = set(wanted_types) & {"PERSON", "ORGANIZATION", "LOCATION", "DATE_TIME", "NRP"}
    if not ner_types:
        return []
    return spacy_entities_to_results(text, ner_types, existing_spans)
