"""Sidecar configuration loaded from environment variables."""

import re

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

# Only allow safe characters in user-visible config strings (alphanumeric,
# hyphens, dots, underscores, slashes, colons, and spaces).
_SAFE_CONFIG_RE = re.compile(r"^[a-zA-Z0-9\s\-._/:]+$")


class SidecarConfig(BaseSettings):
    """All settings are overridable via env vars (e.g. EARLYCORE_API_KEY)."""

    earlycore_api_key: str = ""
    earlycore_endpoint: str = "https://api.earlycore.dev"
    upstream_url: str = "http://agent:8080"
    client_name: str = "AI Agent"
    model_name: str = "claude-sonnet-4-6"
    provider: str = "bedrock"
    region: str = "eu-west-2"
    guardrail_level: str = "moderate"  # strict | moderate | permissive

    @field_validator("client_name", "model_name", "provider", "region", "guardrail_level")
    @classmethod
    def _no_html_in_display_fields(cls, v: str) -> str:
        """Reject values containing HTML/script characters (defense-in-depth)."""
        if not _SAFE_CONFIG_RE.match(v):
            raise ValueError(
                f"Invalid characters in config value {v!r}. "
                "Only alphanumeric, hyphens, dots, underscores, slashes, colons, "
                "and spaces are allowed."
            )
        return v

    block_injection: bool = True
    block_pii: bool = True
    local_pii: bool = True  # True = full Presidio locally; False = regex only, platform handles deep PII
    check_groundedness: bool = True
    fail_open: bool = True  # If guardrails error out, still forward the request
    telemetry_enabled: bool = True
    telemetry_batch_size: int = 10
    telemetry_flush_interval: int = 5  # seconds

    @model_validator(mode="after")
    def _enforce_https_for_telemetry(self) -> "SidecarConfig":
        """Refuse to send API keys over plain HTTP to the EarlyCore platform."""
        if self.earlycore_api_key and not self.earlycore_endpoint.startswith("https://"):
            raise ValueError(
                f"earlycore_endpoint must use HTTPS when an API key is configured "
                f"(got {self.earlycore_endpoint!r}). Refusing to send credentials over HTTP."
            )
        return self
