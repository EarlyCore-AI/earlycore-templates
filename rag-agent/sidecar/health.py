"""Health check endpoint for the sidecar."""

from __future__ import annotations

import httpx
from config import SidecarConfig
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health(config: SidecarConfig | None = None) -> dict:
    """Return sidecar health and upstream agent reachability."""
    config = config or SidecarConfig()
    try:
        async with httpx.AsyncClient(base_url=config.upstream_url, timeout=5.0) as client:
            resp = await client.get("/health")
            agent_status = resp.json() if resp.status_code == 200 else {"status": "unhealthy", "code": resp.status_code}
    except Exception:
        agent_status = "unreachable"

    return {
        "status": "ok" if agent_status != "unreachable" else "degraded",
        "sidecar": "active",
        "agent": agent_status,
    }
