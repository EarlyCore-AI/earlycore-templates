"""Lightweight regex-only PII detection (no Presidio dependency).

Covers the most common PII patterns with sub-5ms latency.
Deep NER-based analysis is deferred to the EarlyCore platform.
"""

from __future__ import annotations

import re

from guardrails import GuardrailResult

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}"), "EMAIL_ADDRESS"),
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "PHONE_NUMBER"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "US_SSN"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "CREDIT_CARD"),
    (re.compile(r"\b[A-Z]{2}\d{2}[ ]?\d{4}[ ]?\d{4}[ ]?\d{4}[ ]?\d{4}[ ]?\d{0,2}\b"), "IBAN_CODE"),
]

_REDACTION_TAG = "<{entity_type}>"


def check_pii(body: bytes) -> GuardrailResult:
    """Scan request body for PII using fast regex patterns."""
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return GuardrailResult(name="pii", blocked=False, reason="decode error")

    found: set[str] = set()
    redacted = text
    for pattern, entity_type in _PATTERNS:
        if pattern.search(text):
            found.add(entity_type)
            redacted = pattern.sub(_REDACTION_TAG.format(entity_type=entity_type), redacted)

    if not found:
        return GuardrailResult(name="pii", blocked=False, reason="clean", confidence=0.0, redacted_text=text)

    return GuardrailResult(
        name="pii",
        blocked=True,
        reason=f"PII detected: {', '.join(sorted(found))}",
        confidence=0.85,
        pii_found=sorted(found),
        redacted_text=redacted,
    )
