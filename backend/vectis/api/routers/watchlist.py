"""Watchlist sync — the client's pins land in the attention registry (Session 38).

The Session-37 frontend persists pins client-side; this endpoint is how they reach the
backend: the tiering engine grants pinned cells their scheduled T1 refresh and T2
priority, eviction protects them, and the viewer's SSE frames carry their off-screen
scores. Pins expire with the viewer (the registry's TTL), so an abandoned browser's
watchlist stops costing compute on its own.

Honesty: pinning affects freshness and priority only — a pinned cell's risk number is
exactly as uncalibrated as everyone else's.
"""

from __future__ import annotations

import h3
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from vectis.realtime.attention import AttentionRegistry

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


class WatchlistSync(BaseModel):
    cells: list[str] = Field(description="Native H3 cell ids currently pinned (full set).")


@router.put("/{viewer_id}")
def sync_watchlist(viewer_id: str, body: WatchlistSync, request: Request) -> dict[str, int]:
    """Replace this viewer's pinned set (idempotent — the client sends the whole list)."""
    for cell_id in body.cells:
        if not h3.is_valid_cell(cell_id):
            raise HTTPException(status_code=422, detail=f"{cell_id!r} is not a valid H3 cell id")
    attention: AttentionRegistry = request.app.state.attention
    attention.set_watchlist(viewer_id, body.cells)
    return {"pinned": len(body.cells)}
