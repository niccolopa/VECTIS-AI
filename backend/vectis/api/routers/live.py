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
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from vectis.api.routers.tiles import TileResponse, serve_tile
from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.realtime.live_stream import GlobalIngestionBroadcaster, LiveStreamBroadcaster

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


def terminal_frame(
    tick: int, tile: TileResponse, events: list[dict[str, Any]],
    *, west: float, south: float, east: float, north: float, zoom: int,
) -> dict[str, Any]:
    """One viewport-scoped terminal frame: global events + the viewport's screened cells.

    The headline is the hottest screened score visible in the viewport (max over every
    hazard of every cell) — a Tier-0 number, honestly absent when nothing is screened.
    """
    headline: float | None = None
    headline_cell: str | None = None
    for cell in tile.cells:
        for score in cell.hazards.values():
            if headline is None or score > headline:
                headline, headline_cell = score, cell.cell_id
    return {
        "tick": tick,
        "ts": datetime.now(UTC).isoformat(),
        "scope": {"west": west, "south": south, "east": east, "north": north, "zoom": zoom},
        "resolution": tile.resolution,
        "cells": [c.model_dump() for c in tile.cells],
        "events": events,  # worldwide, not viewport-filtered — the ticker's tape
        "risk": headline,
        "band": RiskBand.from_score(headline).value if headline is not None else None,
        "cell_id": headline_cell,
    }


@router.get("/terminal")
async def terminal_stream(
    request: Request,
    west: float = Query(ge=-180.0, le=180.0),
    south: float = Query(ge=-90.0, le=90.0),
    east: float = Query(ge=-180.0, le=180.0),
    north: float = Query(ge=-90.0, le=90.0),
    zoom: int = Query(ge=0, le=22),
    frames_limit: int | None = Query(
        default=None, ge=1, alias="frames",
        description="Stop after N frames — for bounded consumers/tests "
        "(the LiveClimateStream.frames(ticks=...) convention). Default: stream forever.",
    ),
) -> StreamingResponse:
    """Viewport-scoped SSE for the global terminal (Session 37).

    One shared :class:`GlobalIngestionBroadcaster` polls the planetary feeds; each
    connection renders the cells visible in *its* viewport from the shared tile store
    via the Session-36 screening-only tile path (cache included) — so a frame can never
    trigger T1/T2 work, and the stream is scoped to what the client actually sees
    instead of one hardcoded demo cell. ponytail: the per-connection screen-per-tick
    still runs N times for N viewers; Session 38's shared broadcast pipeline fixes that.
    """
    broadcaster: GlobalIngestionBroadcaster = request.app.state.global_ingestion
    store, cache = request.app.state.tile_store, request.app.state.tile_cache

    async def frames() -> AsyncIterator[str]:
        tick = 0
        try:
            async for batch in broadcaster.subscribe():
                if await request.is_disconnected():
                    break
                tile = serve_tile(
                    store, cache,
                    west=west, south=south, east=east, north=north, zoom=zoom,
                )
                frame = terminal_frame(
                    tick, tile, batch,
                    west=west, south=south, east=east, north=north, zoom=zoom,
                )
                yield f"data: {json.dumps(frame)}\n\n"
                tick += 1
                if frames_limit is not None and tick >= frames_limit:
                    break
        except asyncio.CancelledError:  # client went away mid-tick
            raise
        finally:
            logger.info("[INFO] v3 terminal stream subscriber closed")

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
