"""Basic output groundedness check — placeholder.

Real groundedness verification requires access to the retrieved documents
that the RAG agent used. This module provides lightweight heuristic flags
that feed into telemetry for the EarlyCore dashboard.
"""

from __future__ import annotations

import re

from guardrails import GuardrailResult

_UNCERTAINTY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bi\s+don'?t\s+know\b", re.I),
    re.compile(r"\bi\s+am\s+not\s+sure\b", re.I),
    re.compile(r"\bi\s+cannot\s+(find|verify|confirm)\b", re.I),
    re.compile(r"\bno\s+(relevant\s+)?information\s+(was\s+)?found\b", re.I),
    re.compile(r"\bbased\s+on\s+my\s+(training|knowledge)\b", re.I),
]

_SOURCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsource[s]?\s*:", re.I),
    re.compile(r"\breference[s]?\s*:", re.I),
    re.compile(r"\baccording\s+to\b", re.I),
    re.compile(r"\bcited\s+from\b", re.I),
]


def check_groundedness(response_body: bytes) -> GuardrailResult:
    """Heuristic groundedness check on agent output.

    Never blocks — only flags for telemetry. Returns a confidence score
    representing how grounded the response appears to be.
    """
    try:
        text = response_body.decode("utf-8", errors="replace")
    except Exception:
        return GuardrailResult(name="groundedness", blocked=False, reason="decode error")

    has_uncertainty = any(p.search(text) for p in _UNCERTAINTY_PATTERNS)
    has_sources = any(p.search(text) for p in _SOURCE_PATTERNS)

    if has_uncertainty and not has_sources:
        return GuardrailResult(name="groundedness", blocked=False, reason="uncertain_no_sources", confidence=0.3)
    if has_sources:
        return GuardrailResult(name="groundedness", blocked=False, reason="has_sources", confidence=0.8)

    return GuardrailResult(name="groundedness", blocked=False, reason="no_signals", confidence=0.5)
