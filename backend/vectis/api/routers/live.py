"""V3 live stream API — Server-Sent Events for the continuous intelligence engine.

``GET /api/v1/stream/v3/live`` opens an SSE channel and drives a fresh
:class:`~vectis.realtime.live_stream.LiveClimateStream` for the connection: every tick
the ramping Liguria feeds advance, the pipeline folds them through Kalman → Bayesian →
Monte Carlo → decision board, and a JSON frame is pushed to the browser.

SSE (not WebSocket) is the right fit here: the flow is strictly server → client, the
native ``EventSource`` reconnects on its own, and a heavy compute loop maps naturally to
an async generator. The generator stops as soon as the client disconnects, tearing the
pipeline down with it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from vectis.core.logging import get_logger
from vectis.realtime.live_stream import LiveClimateStream

router = APIRouter(prefix="/api/v1/stream/v3", tags=["stream-v3"])

logger = get_logger(__name__)


@router.get("/live")
async def live_stream(
    request: Request,
    interval: float = Query(1.5, ge=0.1, le=10.0, description="Seconds between ticks."),
    iterations: int = Query(8_000, ge=1_000, le=100_000, description="Monte Carlo draws/tick."),
) -> StreamingResponse:
    """Stream continuous V3 forecast frames as Server-Sent Events."""
    stream = LiveClimateStream(n_iterations=iterations)

    async def events() -> AsyncIterator[str]:
        try:
            async for frame in stream.frames(tick_seconds=interval):
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(frame)}\n\n"
        except asyncio.CancelledError:  # client went away mid-tick
            raise
        finally:
            logger.info("[INFO] v3 live stream closed")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
