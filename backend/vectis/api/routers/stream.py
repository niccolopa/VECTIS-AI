"""Real-time stream API — ingest events, broadcast state changes.

- ``POST /api/v1/stream/ingest`` accepts a real-world event and returns **202
  Accepted immediately**, handing the (potentially slow) Bayesian-update +
  Monte-Carlo work to a FastAPI ``BackgroundTask``. Ingestion is never blocked by
  calculation — the core async requirement.
- ``GET  /api/v1/stream/state`` returns the current real-time risk picture.
- ``WS   /api/v1/stream/ws`` lets clients subscribe to "state changed" pushes.

The background task is the thin transport adapter: it calls the transport-agnostic
:meth:`RealTimeUpdater.process` (off the event loop, in a worker thread, since the
math is CPU-bound) and publishes the result via the WebSocket broadcaster. Swapping
BackgroundTasks for Celery/Kafka means rewriting only this glue.
"""

from __future__ import annotations

import asyncio

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from vectis.api.deps import get_broadcaster, get_updater
from vectis.digital_twin.schemas import RiskState
from vectis.streaming.broadcaster import ConnectionManager
from vectis.streaming.events import IngestEvent
from vectis.streaming.updater import RealTimeUpdater

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])


async def _process_and_broadcast(
    updater: RealTimeUpdater, broadcaster: ConnectionManager, event: IngestEvent
) -> None:
    """Run the (CPU-bound) update off the loop, then fan-out any state change."""
    change = await asyncio.to_thread(updater.process, event)
    if change is not None:
        await broadcaster.broadcast(change.model_dump(mode="json"))


@router.post("/ingest", status_code=202)
async def ingest_event(
    event: IngestEvent,
    background: BackgroundTasks,
    request: Request,
) -> dict[str, str]:
    """Accept an event and process it asynchronously (HTTP 202)."""
    background.add_task(
        _process_and_broadcast, get_updater(request), get_broadcaster(request), event
    )
    return {"status": "accepted", "event_id": event.event_id}


@router.get("/state")
def current_state(request: Request, region: str = "liguria") -> RiskState:
    """The latest real-time risk picture for a region (synchronous read)."""
    state = get_updater(request).risk_state(region)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No twin registered for '{region}'.")
    return state


@router.websocket("/ws")
async def stream_ws(websocket: WebSocket) -> None:
    """Subscribe to real-time state-change notifications."""
    broadcaster: ConnectionManager = websocket.app.state.broadcaster
    await broadcaster.connect(websocket)
    try:
        # We don't expect inbound messages; receiving keeps the socket open and
        # surfaces disconnects promptly.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(websocket)
