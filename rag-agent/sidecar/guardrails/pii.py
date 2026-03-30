"""PII detection and redaction via Microsoft Presidio.

Uses Presidio Analyzer for detection and Presidio Anonymizer for redaction.
Supports 50+ entity types including names, addresses, phone numbers, credit cards,
medical records, and more.
"""

from __future__ import annotations

from functools import lru_cache

from guardrails import GuardrailResult


@lru_cache(maxsize=1)
def _get_analyzer():
    """Lazy-load and cache the Presidio analyzer engine."""
    from presidio_analyzer import AnalyzerEngine

    return AnalyzerEngine()


@lru_cache(maxsize=1)
def _get_anonymizer():
    """Lazy-load and cache the Presidio anonymizer engine."""
    from presidio_anonymizer import AnonymizerEngine

    return AnonymizerEngine()


# Entity types to detect — Presidio supports 50+, we enable the most relevant.
_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "UK_NHS",
    "IBAN_CODE",
    "PERSON",
    "LOCATION",
    "DATE_TIME",
    "IP_ADDRESS",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "MEDICAL_LICENSE",
    "URL",
]

_SCORE_THRESHOLD = 0.4


def check_pii(body: bytes) -> GuardrailResult:
    """Scan request body for PII using Presidio."""
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return GuardrailResult(name="pii", blocked=False, reason="decode error")

    try:
        analyzer = _get_analyzer()
        results = analyzer.analyze(
            text=text,
            entities=_ENTITIES,
            language="en",
            score_threshold=_SCORE_THRESHOLD,
        )
    except Exception as e:
        return GuardrailResult(name="pii", blocked=False, reason=f"analyzer error: {e}")

    if not results:
        return GuardrailResult(name="pii", blocked=False, reason="clean", confidence=0.0, redacted_text=text)

    try:
        anonymizer = _get_anonymizer()
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        redacted = anonymized.text
    except Exception:
        redacted = text

    found = sorted({r.entity_type for r in results})
    max_score = max(r.score for r in results)

    return GuardrailResult(
        name="pii",
        blocked=True,
        reason=f"PII detected: {', '.join(found)}",
        confidence=max_score,
        pii_found=found,
        redacted_text=redacted,
    )


def redact_pii(text: str) -> str:
    """Apply Presidio redaction to text and return the anonymized version."""
    try:
        analyzer = _get_analyzer()
        anonymizer = _get_anonymizer()
        results = analyzer.analyze(text=text, entities=_ENTITIES, language="en", score_threshold=_SCORE_THRESHOLD)
        if not results:
            return text
        return anonymizer.anonymize(text=text, analyzer_results=results).text
    except Exception:
        return text
