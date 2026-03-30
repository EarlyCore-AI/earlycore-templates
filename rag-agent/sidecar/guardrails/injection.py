"""Prompt injection detection via fast regex pattern matching.

Latency target: <10ms — no LLM calls, pure regex.
"""

from __future__ import annotations

import re

from guardrails import GuardrailResult

# Patterns that strongly indicate prompt injection attempts.
# Each tuple: (compiled regex, human-readable reason, confidence score).
_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "Attempt to override system prompt", 0.95),
    (re.compile(r"ignore\s+(all\s+)?prior\s+instructions", re.I), "Attempt to override system prompt", 0.95),
    (
        re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
        "Attempt to override system prompt",
        0.95,
    ),
    (re.compile(r"you\s+are\s+now\s+", re.I), "Role hijacking attempt", 0.85),
    (re.compile(r"act\s+as\s+(if\s+you\s+are|a)\s+", re.I), "Role hijacking attempt", 0.70),
    (re.compile(r"system\s*:\s*", re.I), "Injected system message", 0.80),
    (re.compile(r"\[system\]", re.I), "Injected system message", 0.80),
    (re.compile(r"<\|im_start\|>", re.I), "ChatML injection", 0.95),
    (re.compile(r"###\s*(system|instruction)", re.I), "Markdown injection", 0.75),
    (re.compile(r"forget\s+(everything|all|what)\s+(you|i)", re.I), "Memory wipe attempt", 0.85),
    (
        re.compile(r"do\s+not\s+follow\s+(your|any)\s+(rules|instructions|guidelines)", re.I),
        "Rule bypass attempt",
        0.90,
    ),
    (
        re.compile(r"reveal\s+(your|the)\s+(system|initial|original)\s+(prompt|instructions)", re.I),
        "Prompt extraction",
        0.90,
    ),
    (re.compile(r"output\s+(your|the)\s+(system|initial)\s+prompt", re.I), "Prompt extraction", 0.90),
]


def check_injection(body: bytes) -> GuardrailResult:
    """Scan request body for prompt injection patterns.

    Returns a ``GuardrailResult`` indicating whether the input should be blocked.
    """
    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        return GuardrailResult(name="injection", blocked=False, reason="decode error", confidence=0.0)

    for pattern, reason, confidence in _PATTERNS:
        if pattern.search(text):
            return GuardrailResult(name="injection", blocked=True, reason=reason, confidence=confidence)

    return GuardrailResult(name="injection", blocked=False, reason="clean", confidence=0.0)
