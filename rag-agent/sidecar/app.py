"""EarlyCore Sidecar — FastAPI reverse proxy with guardrails and telemetry.

Sits between the client and the RAG agent.  Applies input/output guardrails
on the ``/query`` path and forwards all other traffic untouched.  Telemetry
events are sent asynchronously to the EarlyCore platform.
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import pathlib
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from config import SidecarConfig
from fastapi import FastAPI, Request, Response
from guardrails.groundedness import check_groundedness
from guardrails.injection import check_injection
from health import router as health_router
from telemetry.sender import TelemetrySender

logger = logging.getLogger("earlycore.sidecar")

config = SidecarConfig()

if config.local_pii:
    from guardrails.pii import check_pii
else:
    from guardrails.pii_lite import check_pii
telemetry = TelemetrySender(config)
client: httpx.AsyncClient


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global client
    client = httpx.AsyncClient(base_url=config.upstream_url, timeout=120.0)
    if config.telemetry_enabled:
        await telemetry.start()
    yield
    await telemetry.stop()
    await client.aclose()


app = FastAPI(title="EarlyCore Sidecar", lifespan=lifespan)
app.include_router(health_router)

_DASHBOARD_TEMPLATE = (pathlib.Path(__file__).parent / "dashboard.html").read_text()


def _safe(value: str) -> str:
    """HTML-escape a value to prevent template injection / XSS."""
    return html.escape(str(value), quote=True)


@app.get("/", response_class=Response)
async def dashboard() -> Response:
    """Serve the EarlyCore security dashboard with live config values injected."""
    page = _DASHBOARD_TEMPLATE
    page = page.replace("{{ client_name }}", _safe(config.client_name))
    page = page.replace("{{ guardrail_level }}", _safe(config.guardrail_level))
    page = page.replace("{{ upstream_url }}", _safe(config.upstream_url))
    page = page.replace("{{ injection_status }}", "Active" if config.block_injection else "Inactive")
    page = page.replace("{{ pii_status }}", "Active" if config.block_pii else "Inactive")
    page = page.replace("{{ groundedness_status }}", "Active" if config.check_groundedness else "Inactive")
    page = page.replace("{{ telemetry_status }}", "Active" if config.telemetry_enabled else "Inactive")
    page = page.replace("{{ fail_mode }}", "Open" if config.fail_open else "Closed")
    page = page.replace("{{ model_name }}", _safe(config.model_name))
    page = page.replace("{{ provider }}", _safe(config.provider))
    page = page.replace("{{ region }}", _safe(config.region))
    page = page.replace("{{ guardrail_preset }}", _safe(config.guardrail_level.title()))
    return Response(content=page, media_type="text/html")


# In-memory stats counter for the dashboard
_stats: dict = {"total": 0, "blocked": 0, "pii_redacted": 0, "requests": []}


@app.get("/api/stats")
async def api_stats() -> dict:
    """Return live sidecar metrics for the dashboard."""
    return {
        "total": _stats["total"],
        "blocked": _stats["blocked"],
        "pii_redacted": _stats["pii_redacted"],
        "recent": _stats["requests"][-50:],
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str) -> Response:
    """Reverse-proxy with per-path guardrails."""
    request_id = str(uuid.uuid4())
    start_time = time.monotonic()

    body = await request.body()

    # ---- INPUT guardrails (only on POST /query) ----
    injection_blocked = False
    pii_blocked = False
    guardrail_results: dict = {}
    is_query = path == "query" and request.method == "POST"

    if is_query:
        if config.block_injection:
            injection_result = check_injection(body)
            guardrail_results["injection"] = injection_result
            if injection_result.blocked:
                injection_blocked = True

        if config.block_pii:
            pii_result = check_pii(body)
            guardrail_results["pii"] = pii_result
            if pii_result.blocked:
                pii_blocked = True
                # Use redacted text for forwarding if we aren't hard-blocking.
                if config.fail_open and pii_result.redacted_text:
                    body = pii_result.redacted_text.encode("utf-8")

    # Injection attempts are ALWAYS hard-blocked (never fail-open).
    # PII blocks respect the fail_open setting (redacted text is forwarded).
    hard_blocked = injection_blocked or (pii_blocked and not config.fail_open)
    blocked = injection_blocked or pii_blocked

    if hard_blocked:
        details = {k: v.to_dict() for k, v in guardrail_results.items() if v.blocked}
        payload = json.dumps({"error": "Request blocked by security guardrails", "details": details})
        _emit_telemetry(request_id, path, request.method, 403, start_time, guardrail_results, blocked=True)
        return Response(
            content=payload,
            status_code=403,
            media_type="application/json",
            headers={"x-earlycore-request-id": request_id},
        )

    # ---- Forward to upstream agent ----
    upstream_headers = {
        "content-type": request.headers.get("content-type", "application/json"),
        "x-earlycore-request-id": request_id,
    }
    try:
        response = await client.request(
            method=request.method,
            url=f"/{path}",
            content=body,
            headers=upstream_headers,
        )
    except httpx.HTTPError as exc:
        logger.error("Upstream unreachable: %s", exc)
        _emit_telemetry(request_id, path, request.method, 502, start_time, guardrail_results, blocked=False)
        return Response(
            content=json.dumps({"error": "Upstream agent unreachable"}),
            status_code=502,
            media_type="application/json",
            headers={"x-earlycore-request-id": request_id},
        )

    # ---- OUTPUT guardrails ----
    response_body = response.content
    if is_query and config.check_groundedness:
        ground_result = check_groundedness(response_body)
        guardrail_results["groundedness"] = ground_result

    # ---- Telemetry (async, non-blocking) ----
    _emit_telemetry(request_id, path, request.method, response.status_code, start_time, guardrail_results, blocked)

    return Response(
        content=response_body,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
        headers={"x-earlycore-request-id": request_id},
    )


def _emit_telemetry(
    request_id: str,
    path: str,
    method: str,
    status_code: int,
    start_time: float,
    guardrail_results: dict,
    blocked: bool,
) -> None:
    elapsed = time.monotonic() - start_time
    latency_ms = round(elapsed * 1000)

    # Always record to in-memory stats for the dashboard
    _stats["total"] += 1
    if blocked:
        _stats["blocked"] += 1
    if "pii" in guardrail_results and guardrail_results["pii"].blocked:
        _stats["pii_redacted"] += 1

    tags = []
    for k, v in guardrail_results.items():
        tags.append(f"{'blocked' if v.blocked else 'pass'}:{k}")
    if not tags:
        tags = ["pass"]

    _stats["requests"].append(
        {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "path": f"/{path}",
            "status": status_code,
            "latency": f"{latency_ms}ms",
            "tags": tags,
        }
    )
    if len(_stats["requests"]) > 100:
        _stats["requests"] = _stats["requests"][-50:]

    if not config.telemetry_enabled:
        return
    telemetry.record(
        request_id=request_id,
        path=path,
        method=method,
        status_code=status_code,
        latency_ms=latency_ms,
        guardrail_results=guardrail_results,
        blocked=blocked,
    )
