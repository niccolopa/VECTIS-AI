"""V3 live stream API — Server-Sent Events over the single global intelligence engine.

``GET /api/v1/stream/v3/live`` opens an SSE channel and **subscribes** to the one
:class:`~vectis.realtime.live_stream.LiveStreamBroadcaster` started at app startup. The
heavy pipeline (Kalman → Bayesian → Monte Carlo → decision board) runs exactly once as a
background task; each connection is a lightweight fan-out subscriber, so a thousand open
dashboards cost one pipeline, not a thousand concurrent Monte Carlo engines.

SSE (not WebSocket) is the right fit here: the flow is strictly server → client, the native
``EventSource`` reconnects on its own, and a new viewer is handed the latest frame on connect.
The generator stops as soon as the client disconnects, dropping only its subscription.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from vectis.core.logging import get_logger
from vectis.realtime.live_stream import LiveStreamBroadcaster

router = APIRouter(prefix="/api/v1/stream/v3", tags=["stream-v3"])

logger = get_logger(__name__)


@router.get("/live")
async def live_stream(request: Request) -> StreamingResponse:
    """Stream continuous V3 forecast frames as Server-Sent Events (shared pipeline)."""
    broadcaster: LiveStreamBroadcaster = request.app.state.live_stream

    async def events() -> AsyncIterator[str]:
        try:
            async for frame in broadcaster.subscribe():
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(frame)}\n\n"
        except asyncio.CancelledError:  # client went away mid-tick
            raise
        finally:
            logger.info("[INFO] v3 live stream subscriber closed")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
