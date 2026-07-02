"""H3-aggregated map tiles — the cheap, screening-only view the global map renders.

Given a viewport bbox + web-map zoom level, resolve the H3 resolution a renderer wants
and return per-cell risk for every screened hazard. The **only** risk source is the
Session-32 :class:`GlobalScreeningSweep` — the near-free vectorized point estimate over
the active cell set. This module must **never** import or trigger the expensive T1/T2
machinery (the Monte Carlo engine, the Bayesian pipeline, the decision board): tiles are
a *view* of the screen, and promotion to deep analysis stays the tiering engine's job.

Zoom → H3 resolution (the exact mapping)
----------------------------------------
Native grid data lives at H3 **res 5** (Session 30, ~8.5 km cells). Web-map zoom levels
map to H3 resolutions so one H3 cell stays a sensible on-screen size (H3 res ≈ good for
~2 zoom levels, since each res step is ~√7 ≈ 2.6× finer while a zoom step is 2×):

    ==========  ============  =========================================
    zoom        H3 res        what the viewer sees
    ==========  ============  =========================================
    0–2         2             whole-globe overview (coarse roll-up)
    3–4         3             continental (roll-up)
    5–6         4             regional (roll-up)
    7–8         5             native grid resolution (the screened cells)
    9–10        6             street-ish (display subdivision)
    11+         7             finest served (display subdivision)
    ==========  ============  =========================================

Resolutions **coarser** than 5 are a fine-to-coarse roll-up: children collapse onto
their res-N parent taking the **max** per hazard (a hot child must never be averaged
away — the map is a risk screen, not a mean). Resolutions **finer** than 5 subdivide a
native cell into its children, each inheriting the parent's score — pure display
subdivision that adds no information (the data's resolution floor is 5, and saying
otherwise would fabricate precision).

Honesty: scores inherit the models' illustrative, uncalibrated coefficients — a tile
existing is not validation.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

import h3
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from vectis.realtime.screening.base import UNSCREENED_HAZARDS, default_registry
from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.state.cell_id import DEFAULT_RESOLUTION, children_cell_ids, parent_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore

router = APIRouter(prefix="/api/v1/tiles", tags=["tiles"])

#: (max zoom, H3 res) breakpoints of the documented mapping above, checked in order.
_ZOOM_BREAKS: tuple[tuple[int, int], ...] = ((2, 2), (4, 3), (6, 4), (8, 5), (10, 6))
_FINEST_RES = 7


def h3_resolution_for_zoom(zoom: int) -> int:
    """The documented zoom→resolution mapping: res 2 zoomed out … res 7 zoomed in."""
    for max_zoom, res in _ZOOM_BREAKS:
        if zoom <= max_zoom:
            return res
    return _FINEST_RES


#: Plain-dict center cache (cells never move). A dict lookup beats an lru_cache call on
#: the tile hot path, where every request scans the whole active set once.
_CENTERS: dict[str, tuple[float, float]] = {}


def _cell_center(cell_id: str) -> tuple[float, float]:
    """(lat, lon) center of an H3 cell — cached, cells never move."""
    center = _CENTERS.get(cell_id)
    if center is None:
        center = _CENTERS[cell_id] = h3.cell_to_latlng(cell_id)
    return center


def cells_in_bbox(
    states: list[WorldCellState], west: float, south: float, east: float, north: float
) -> list[WorldCellState]:
    """Active cells whose center falls inside the viewport bbox.

    ponytail: center-point test, no antimeridian handling — a cell straddling the bbox
    edge (or a viewport crossing ±180°) can be missed; split the bbox client-side.
    O(hot set) per request; move to a spatial index if the hot set outgrows ~100k cells.
    """
    centers = _CENTERS
    missing = [s.cell_id for s in states if s.cell_id not in centers]
    for cell_id in missing:
        centers[cell_id] = h3.cell_to_latlng(cell_id)
    return [
        s for s in states
        if south <= centers[s.cell_id][0] <= north and west <= centers[s.cell_id][1] <= east
    ]


class TileCell(BaseModel):
    """One rendered cell: where it is and each screened hazard's 0–100 score."""

    cell_id: str
    lat: float
    lon: float
    hazards: dict[str, float]
    source_cells: int = Field(
        description="Native res-5 cells this entry aggregates (1 at res ≥ 5)."
    )


class TileResponse(BaseModel):
    zoom: int
    resolution: int
    cells: list[TileCell]


def build_tile(
    states: list[WorldCellState], resolution: int, hazard: str | None = None
) -> list[TileCell]:
    """Screen the given native cells and re-grid the scores to ``resolution``.

    Screening-sourced only: one :class:`GlobalScreeningSweep` pass (a vectorized point
    estimate per registered hazard) — no sampling, no promotion, no board.
    """
    sweep = GlobalScreeningSweep().sweep(states)

    # {target cell → {hazard → score}} plus how many native cells fed each target.
    aggregated: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for cell_id, scores in sweep.items():
        wanted = {h: s.value for h, s in scores.items() if hazard is None or h == hazard}
        if not wanted:
            continue
        if resolution < DEFAULT_RESOLUTION:
            targets = [parent_cell_id(cell_id, resolution)]  # fine-to-coarse roll-up
        elif resolution > DEFAULT_RESOLUTION:
            targets = children_cell_ids(cell_id, resolution)  # display subdivision
        else:
            targets = [cell_id]
        for target in targets:
            bucket = aggregated.setdefault(target, {})
            for hz, value in wanted.items():
                # Max per hazard: a hot child must never be averaged away (see module doc).
                bucket[hz] = max(bucket.get(hz, 0.0), value)
            counts[target] = counts.get(target, 0) + 1

    cells = []
    for target, hazards in sorted(aggregated.items()):
        lat, lon = _cell_center(target)
        cells.append(
            TileCell(
                cell_id=target, lat=lat, lon=lon, hazards=hazards,
                source_cells=counts[target],
            )
        )
    return cells


#: One cached tile: when it was computed, which native cells contributed, the state
#: version each contributor had, and the finished cells. The (ids, versions) pair is the
#: entry's validity fingerprint — logically the cache is keyed on (bbox, zoom, hazard,
#: each contributing cell's state version); the versions live in the entry so a hit can
#: be validated with O(visible) point reads instead of an O(hot set) rescan.
_TileEntry = tuple[float, list[str], tuple[int, ...], list[TileCell]]


class TileCache:
    """TTL + LRU cache of computed tiles — the ``SimulationCache`` pattern, tile-shaped.

    Invalidation is structural: a real update to a contributing cell bumps its state
    version, the entry's fingerprint no longer matches, and exactly the viewports that
    cell contributes to recompute — every other tile keeps hitting. TTL bounds what the
    fingerprint can't see (a cell *born* into a cached viewport shows up after at most
    ``ttl_seconds``; a swapped calibration artifact likewise). LRU bounds memory.
    """

    def __init__(self, *, maxsize: int = 1024, ttl_seconds: float = 30.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, _TileEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(
        self,
        key: str,
        current_versions: Callable[[list[str]], tuple[int, ...]],
        *,
        now: float | None = None,
    ) -> list[TileCell] | None:
        """The cached cells for ``key`` — only if unexpired **and** every contributing
        cell still has the state version it was computed from."""
        now = time.monotonic() if now is None else now
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        stored_at, member_ids, versions, cells = entry
        if now - stored_at > self._ttl or current_versions(member_ids) != versions:
            del self._store[key]  # expired, or a contributing cell moved on
            self.misses += 1
            return None
        self._store.move_to_end(key)  # LRU touch
        self.hits += 1
        return cells

    def put(
        self,
        key: str,
        member_ids: list[str],
        versions: tuple[int, ...],
        cells: list[TileCell],
        *,
        now: float | None = None,
    ) -> None:
        now = time.monotonic() if now is None else now
        self._store[key] = (now, member_ids, versions, cells)
        self._store.move_to_end(key)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)  # evict least-recently-used

    def __len__(self) -> int:
        return len(self._store)


def serve_tile(
    store: StateStore[WorldCellState],
    cache: TileCache,
    *,
    west: float, south: float, east: float, north: float,
    zoom: int, hazard: str | None = None,
) -> TileResponse:
    """The endpoint's whole computation, seam-exposed for direct load-testing.

    Hit path: one lookup + O(visible) version reads — no sweep, no full-store scan.
    ponytail: on an EvictingStateStore the per-cell version reads touch LRU recency,
    keeping viewed cells warm — acceptable (viewed cells *are* in use).
    """
    key = f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}|{zoom}|{hazard or '*'}"

    def current_versions(member_ids: list[str]) -> tuple[int, ...]:
        get_state = store.get_state
        # A vanished (evicted) cell reads as -1: never a real version, so a fresh miss.
        return tuple(
            state.version if (state := get_state(cid)) is not None else -1
            for cid in member_ids
        )

    resolution = h3_resolution_for_zoom(zoom)
    cells = cache.get(key, current_versions)
    if cells is None:
        visible = cells_in_bbox(store.active_states(), west, south, east, north)
        cells = build_tile(visible, resolution, hazard)
        cache.put(
            key,
            [s.cell_id for s in visible],
            tuple(s.version for s in visible),
            cells,
        )
    # model_construct: the cells were validated at build time; don't re-pay per request.
    return TileResponse.model_construct(zoom=zoom, resolution=resolution, cells=cells)


@router.get("", response_model=TileResponse)
def get_tiles(
    request: Request,
    west: float = Query(ge=-180.0, le=180.0),
    south: float = Query(ge=-90.0, le=90.0),
    east: float = Query(ge=-180.0, le=180.0),
    north: float = Query(ge=-90.0, le=90.0),
    zoom: int = Query(ge=0, le=22),
    hazard: str | None = Query(default=None, description="Limit to one screened hazard."),
) -> TileResponse:
    """Per-cell screened risk for the viewport, re-gridded to the zoom's H3 resolution."""
    if hazard is not None and hazard not in default_registry():
        detail = (
            f"hazard {hazard!r} is observed but has no screening model yet"
            if hazard in UNSCREENED_HAZARDS
            else f"unknown hazard {hazard!r}"
        )
        raise HTTPException(status_code=404, detail=detail)

    return serve_tile(
        request.app.state.tile_store, request.app.state.tile_cache,
        west=west, south=south, east=east, north=north, zoom=zoom, hazard=hazard,
    )
