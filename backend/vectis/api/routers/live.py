"""Global terminal stream API — viewport-scoped Server-Sent Events.

``GET /api/v1/stream/v3/terminal`` subscribes one terminal viewer to the single
:class:`~vectis.realtime.live_stream.GlobalIngestionBroadcaster` started at app
startup; each connection is a lightweight fan-out queue re-gridding the shared
compute loop's scores to its own viewport.

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
from uuid import uuid4

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from vectis.api.routers.tiles import TileCell, _cell_center, h3_resolution_for_zoom, regrid
from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.realtime.attention import AttentionRegistry
from vectis.realtime.compute import SharedComputeLoop
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.state.cell_id import DEFAULT_RESOLUTION

router = APIRouter(prefix="/api/v1/stream/v3", tags=["stream-v3"])

logger = get_logger(__name__)


def terminal_frame(
    tick: int, cells: list[TileCell], resolution: int, events: list[dict[str, Any]],
    *, west: float, south: float, east: float, north: float, zoom: int,
    watchlist_cells: list[TileCell] | None = None,
) -> dict[str, Any]:
    """One viewport-scoped terminal frame: global events + the viewport's screened cells.

    The headline is the hottest screened score visible in the viewport (max over every
    hazard of every cell) — a Tier-0 number, honestly absent when nothing is screened.
    ``watchlist_cells`` (Session 38) carries the viewer's pinned cells that fall
    *outside* the viewport, so the watchlist panel stays fresh without widening the map
    scope — the subscription is viewport + pins, never the global firehose.
    """
    headline: float | None = None
    headline_cell: str | None = None
    for cell in cells:
        for score in cell.hazards.values():
            if headline is None or score > headline:
                headline, headline_cell = score, cell.cell_id
    return {
        "tick": tick,
        "ts": datetime.now(UTC).isoformat(),
        "scope": {"west": west, "south": south, "east": east, "north": north, "zoom": zoom},
        "resolution": resolution,
        "cells": [c.model_dump() for c in cells],
        "watchlist_cells": [c.model_dump() for c in (watchlist_cells or [])],
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
        description="Stop after N frames — for bounded consumers/tests. "
        "Default: stream forever.",
    ),
    viewer: str | None = Query(
        default=None,
        description="Stable viewer id (the client's persisted uuid). Registers this "
        "connection's viewport in the attention registry and scopes the frames to "
        "viewport + this viewer's watchlist pins.",
    ),
) -> StreamingResponse:
    """Viewport-scoped SSE for the global terminal (Sessions 37–38).

    The shared compute loop screens the planet once per tick; each connection is a
    **fan-out subscriber** that re-grids the already-computed scores to its own
    viewport (cheap arithmetic, no per-connection sweep — the Session-37 ``ponytail``
    debt, closed). Connecting registers the viewport as attention: visible cells are
    exempt from idle eviction and screened every tick while watched. A vanished client
    is forgotten by the registry's viewer TTL — no explicit drop on disconnect, so a
    pan's reconnect under the same viewer id can never race its own attention away.
    """
    broadcaster: GlobalIngestionBroadcaster = request.app.state.global_ingestion
    compute: SharedComputeLoop = request.app.state.compute
    attention: AttentionRegistry = request.app.state.attention
    viewer_id = viewer or f"anon-{uuid4().hex[:12]}"
    attention.set_viewport(viewer_id, west=west, south=south, east=east, north=north)
    resolution = h3_resolution_for_zoom(zoom)

    def build_frame(tick: int, batch: list[dict[str, Any]]) -> dict[str, Any]:
        attention.touch(viewer_id)
        latest = compute.latest_scores
        visible = {
            cell_id: scores
            for cell_id, scores in latest.items()
            if (center := _cell_center(cell_id))
            and south <= center[0] <= north and west <= center[1] <= east
        }
        pins = attention.watchlist_of(viewer_id)
        off_screen = {c: latest[c] for c in pins if c in latest and c not in visible}
        return terminal_frame(
            tick, regrid(visible, resolution), resolution, batch,
            west=west, south=south, east=east, north=north, zoom=zoom,
            watchlist_cells=regrid(off_screen, DEFAULT_RESOLUTION) if off_screen else None,
        )

    async def frames() -> AsyncIterator[str]:
        tick = 0
        try:
            async for batch in broadcaster.subscribe():
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(build_frame(tick, batch))}\n\n"
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
