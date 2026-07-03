"""Viewer attention — which cells someone is actually looking at right now.

Session 38's first primitive. Until now the system had no concept of "a user is
currently looking at this cell": eviction was pure TTL+LRU, and every active cell was
screened at the same cadence regardless of whether anyone could see it. This module is
the explicit attention signal:

- each connected terminal registers its **viewport bbox** (from the Session-37 map) and
  its **watchlist** (the Session-37 pins) under a viewer id;
- :meth:`AttentionRegistry.protects` tells the :class:`EvictingStateStore` which cells
  are exempt from idle-TTL eviction while watched;
- :func:`warming_partition` tells the shared compute loop which cells to screen every
  tick (attended) versus on the slower full-sweep cadence (everything else).

Honesty note: attention affects **freshness and retention only**. A watched cell's risk
number comes from the same uncalibrated models as an unwatched one — being looked at
does not make a score more accurate, and nothing here implies otherwise.

Viewers are expired after ``viewer_ttl_seconds`` without a refresh, so a crashed
connection that never unregistered cannot pin cells warm forever.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Sequence

import h3

from vectis.realtime.events.base import CellId
from vectis.realtime.state.models import WorldCellState

#: How long a registered viewer stays valid without a refresh. SSE reconnects and
#: viewport changes both refresh; a dead client ages out in about two minutes.
DEFAULT_VIEWER_TTL = 120.0

#: Unattended cells are still screened, just less often: every Nth compute tick.
#: Attended cells are screened every tick. ponytail: hand-set cadence; make it
#: adaptive if full sweeps ever dominate cycle time at planetary hot-set sizes.
FULL_SWEEP_EVERY = 5

_Bbox = tuple[float, float, float, float]  # (west, south, east, north)

#: Cell centers never move — same plain-dict cache pattern as the tile router.
_CENTERS: dict[str, tuple[float, float]] = {}


def _cell_center(cell_id: str) -> tuple[float, float]:
    center = _CENTERS.get(cell_id)
    if center is None:
        center = _CENTERS[cell_id] = h3.cell_to_latlng(cell_id)
    return center


class AttentionRegistry:
    """Thread-safe registry of who is looking where (viewports) and at what (watchlists).

    The compute loop reads it every cycle; SSE handlers write it on connect, viewport
    change, and disconnect; the watchlist API writes pins. All reads purge expired
    viewers first, so a vanished client's attention decays on its own.
    """

    def __init__(
        self,
        *,
        viewer_ttl_seconds: float = DEFAULT_VIEWER_TTL,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = viewer_ttl_seconds
        self._now = time_fn
        self._lock = threading.Lock()
        self._viewports: dict[str, _Bbox] = {}
        self._watchlists: dict[str, frozenset[CellId]] = {}
        self._last_seen: dict[str, float] = {}

    # ── writes (SSE handlers / watchlist API) ────────────────────────────────────
    def set_viewport(
        self, viewer_id: str, *, west: float, south: float, east: float, north: float
    ) -> None:
        """Register/refresh a viewer's current viewport bbox."""
        with self._lock:
            self._viewports[viewer_id] = (west, south, east, north)
            self._last_seen[viewer_id] = self._now()

    def set_watchlist(self, viewer_id: str, cells: Iterable[CellId]) -> None:
        """Register/refresh a viewer's pinned cells (native res-5 ids)."""
        with self._lock:
            self._watchlists[viewer_id] = frozenset(cells)
            self._last_seen[viewer_id] = self._now()

    def touch(self, viewer_id: str) -> None:
        """Keep a known viewer alive without changing its viewport/watchlist."""
        with self._lock:
            if viewer_id in self._last_seen:
                self._last_seen[viewer_id] = self._now()

    def drop(self, viewer_id: str) -> None:
        """Forget a viewer entirely (clean disconnect)."""
        with self._lock:
            self._viewports.pop(viewer_id, None)
            self._watchlists.pop(viewer_id, None)
            self._last_seen.pop(viewer_id, None)

    # ── reads (compute loop / eviction) ──────────────────────────────────────────
    def _purge_expired_locked(self) -> None:
        now = self._now()
        for viewer_id in [v for v, ts in self._last_seen.items() if now - ts > self._ttl]:
            self._viewports.pop(viewer_id, None)
            self._watchlists.pop(viewer_id, None)
            self._last_seen.pop(viewer_id, None)

    @property
    def viewer_count(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            return len(self._last_seen)

    def watchlisted(self) -> set[CellId]:
        """Every cell pinned by any live viewer."""
        with self._lock:
            self._purge_expired_locked()
            return set().union(*self._watchlists.values()) if self._watchlists else set()

    def is_attended(self, lat: float, lon: float) -> bool:
        """True if any live viewport contains the point.

        Same center-point containment as the tile bbox filter (ponytail: no
        antimeridian handling — a viewport crossing ±180° is split client-side).
        """
        with self._lock:
            self._purge_expired_locked()
            return any(
                south <= lat <= north and west <= lon <= east
                for west, south, east, north in self._viewports.values()
            )

    def protects(self, cell_id: CellId) -> bool:
        """Should this cell be exempt from idle-TTL eviction right now?

        True when the cell is inside a live viewport **or** on a live watchlist —
        the predicate :class:`EvictingStateStore` consults before evicting.
        """
        with self._lock:
            self._purge_expired_locked()
            if any(cell_id in pins for pins in self._watchlists.values()):
                return True
            if not self._viewports:
                return False
            lat, lon = _cell_center(cell_id)
            return any(
                south <= lat <= north and west <= lon <= east
                for west, south, east, north in self._viewports.values()
            )

    def attended_cells(self, states: Sequence[WorldCellState]) -> set[CellId]:
        """The subset of ``states`` currently inside a viewport or on a watchlist."""
        with self._lock:
            self._purge_expired_locked()
            viewports = list(self._viewports.values())
            pins: set[CellId] = (
                set().union(*self._watchlists.values()) if self._watchlists else set()
            )
        attended: set[CellId] = set()
        for state in states:
            if state.cell_id in pins:
                attended.add(state.cell_id)
                continue
            lat, lon = _cell_center(state.cell_id)
            if any(
                south <= lat <= north and west <= lon <= east
                for west, south, east, north in viewports
            ):
                attended.add(state.cell_id)
        return attended


def warming_partition(
    tick: int,
    states: Sequence[WorldCellState],
    registry: AttentionRegistry,
    *,
    full_sweep_every: int = FULL_SWEEP_EVERY,
) -> list[WorldCellState]:
    """The cells the compute loop should screen on this tick.

    Attended cells (visible or pinned) are screened **every** tick — the warming path.
    Everything else joins only on the full-sweep cadence (every ``full_sweep_every``-th
    tick), which preserves today's behavior for the truly dormant case: a cell nobody
    watches and nothing updates is screened at the background cadence and ages toward
    eviction exactly as before.
    """
    if full_sweep_every <= 1 or tick % full_sweep_every == 0:
        return list(states)
    attended = registry.attended_cells(states)
    return [s for s in states if s.cell_id in attended]


def demo() -> None:
    """Self-check: viewport + pin attention, viewer expiry, and the warming cadence."""
    clock = [0.0]
    reg = AttentionRegistry(viewer_ttl_seconds=60.0, time_fn=lambda: clock[0])
    inside = WorldCellState(cell_id=h3.latlng_to_cell(37.0, -120.0, 5))
    outside = WorldCellState(cell_id=h3.latlng_to_cell(-33.4, 150.3, 5))
    pinned = WorldCellState(cell_id=h3.latlng_to_cell(38.5, 23.6, 5))

    reg.set_viewport("a", west=-125.0, south=32.0, east=-114.0, north=42.0)
    reg.set_watchlist("b", {pinned.cell_id})
    assert reg.protects(inside.cell_id) and reg.protects(pinned.cell_id)
    assert not reg.protects(outside.cell_id)
    assert reg.attended_cells([inside, outside, pinned]) == {inside.cell_id, pinned.cell_id}

    # Off-cadence tick: only attended cells are screened; on-cadence: everyone.
    assert {s.cell_id for s in warming_partition(1, [inside, outside, pinned], reg)} == {
        inside.cell_id, pinned.cell_id
    }
    assert len(warming_partition(FULL_SWEEP_EVERY, [inside, outside, pinned], reg)) == 3

    clock[0] = 61.0  # both viewers expire → nothing is protected any more
    assert not reg.protects(inside.cell_id) and reg.viewer_count == 0
    print("OK")


if __name__ == "__main__":
    demo()
