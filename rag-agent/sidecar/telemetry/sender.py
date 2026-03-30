"""Non-blocking telemetry sender for the EarlyCore platform.

Buffers events in memory and flushes them in a background task to
``{earlycore_endpoint}/api/v1/telemetry/ingest``.  If the platform is
unreachable the buffer is retained and retried on the next flush cycle.
The request path is never blocked by telemetry.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from config import SidecarConfig

logger = logging.getLogger("earlycore.telemetry")


_MAX_BUFFER_SIZE = 1000  # Cap to prevent unbounded memory growth when telemetry endpoint is unreachable.


class TelemetrySender:
    """Batched, async telemetry sender."""

    def __init__(self, config: SidecarConfig) -> None:
        self._config = config
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None
        self._url = f"{config.earlycore_endpoint.rstrip('/')}/api/v1/telemetry/ingest"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        request_id: str,
        path: str,
        method: str,
        status_code: int,
        latency_ms: float,
        guardrail_results: dict[str, Any] | None = None,
        blocked: bool = False,
    ) -> None:
        """Enqueue a telemetry event (non-blocking, sync-safe)."""
        event = {
            "request_id": request_id,
            "path": path,
            "method": method,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "guardrail_results": {k: v.to_dict() for k, v in (guardrail_results or {}).items()},
            "blocked": blocked,
            "timestamp": time.time(),
        }
        # Append is thread-safe for CPython, but we flush under a lock.
        # Drop oldest events when buffer is full to prevent unbounded memory growth.
        if len(self._buffer) >= _MAX_BUFFER_SIZE:
            self._buffer = self._buffer[len(self._buffer) - _MAX_BUFFER_SIZE + 1 :]
        self._buffer.append(event)

    async def start(self) -> None:
        """Start the background flush loop."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        """Flush remaining events and cancel the background task."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        await self._flush_once()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.telemetry_flush_interval)
            await self._flush_once()

    async def _flush_once(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[: self._config.telemetry_batch_size]
            self._buffer = self._buffer[self._config.telemetry_batch_size :]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._url,
                    json={"events": batch},
                    headers={"Authorization": f"Bearer {self._config.earlycore_api_key}"},
                )
                if resp.status_code >= 400:
                    logger.warning("Telemetry flush failed: %s %s", resp.status_code, resp.text[:200])
                    # Re-queue events so they are retried next cycle.
                    async with self._lock:
                        self._buffer = batch + self._buffer
        except Exception:
            logger.warning("Telemetry endpoint unreachable — buffering %d events", len(batch), exc_info=False)
            async with self._lock:
                self._buffer = batch + self._buffer
