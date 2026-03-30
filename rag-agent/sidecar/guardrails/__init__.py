"""Guardrail checks applied to inbound and outbound traffic."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    """Outcome of a single guardrail check."""

    name: str
    blocked: bool = False
    reason: str = ""
    confidence: float = 0.0
    pii_found: list[str] = field(default_factory=list)
    redacted_text: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "blocked": self.blocked,
            "reason": self.reason,
            "confidence": self.confidence,
            "pii_found": self.pii_found,
        }
