"""Session 38 — viewport-aware attention: eviction exemption and the warming cadence.

Attention affects freshness and retention only — none of this changes any risk number.
"""

from __future__ import annotations

import h3

from vectis.realtime.attention import (
    FULL_SWEEP_EVERY,
    AttentionRegistry,
    warming_partition,
)
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore

CALIFORNIA = h3.latlng_to_cell(37.0, -120.0, 5)
NSW = h3.latlng_to_cell(-33.4, 150.3, 5)
ATTICA = h3.latlng_to_cell(38.5, 23.6, 5)

#: A viewport over California only.
CA_VIEW = {"west": -125.0, "south": 32.0, "east": -114.0, "north": 42.0}


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _store(clock: _Clock, registry: AttentionRegistry | None, **kwargs):
    keep = registry.protects if registry is not None else None
    return EvictingStateStore(
        MemoryStateStore[WorldCellState](), idle_seconds=100.0, time_fn=clock, keep=keep, **kwargs
    )


def test_attended_cell_survives_the_ttl_that_evicts_its_unwatched_twin() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    registry.set_viewport("viewer", **CA_VIEW)
    store = _store(clock, registry)

    store.save_state(WorldCellState(cell_id=CALIFORNIA))
    store.save_state(WorldCellState(cell_id=NSW))
    clock.now = 150.0  # both past the 100 s idle TTL
    ids = store.active_cell_ids()

    assert CALIFORNIA in ids, "watched cell must be exempt from idle eviction"
    assert NSW not in ids, "the unwatched twin evicts exactly as before"


def test_cell_starts_aging_again_the_moment_attention_moves_away() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    registry.set_viewport("viewer", **CA_VIEW)
    store = _store(clock, registry)

    store.save_state(WorldCellState(cell_id=CALIFORNIA))
    clock.now = 150.0
    assert CALIFORNIA in store.active_cell_ids()  # protected (and re-warmed at t=150)

    registry.drop("viewer")  # attention gone; the cell ages from its last re-warm
    clock.now = 200.0
    assert CALIFORNIA in store.active_cell_ids()  # only 50 s idle since re-warm
    clock.now = 300.0
    assert CALIFORNIA not in store.active_cell_ids()  # 150 s idle → evicted normally


def test_watchlist_pin_protects_a_cell_no_viewport_covers() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    registry.set_watchlist("viewer", {ATTICA})
    store = _store(clock, registry)

    store.save_state(WorldCellState(cell_id=ATTICA))
    clock.now = 150.0
    assert ATTICA in store.active_cell_ids()


def test_no_registry_means_exactly_the_old_eviction_behavior() -> None:
    clock = _Clock()
    store = _store(clock, None)
    store.save_state(WorldCellState(cell_id=CALIFORNIA))
    clock.now = 150.0
    assert store.active_cell_ids() == []


def test_the_lru_memory_bound_is_hard_even_when_everything_is_protected() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    # A planet-wide viewport: every cell is attended.
    registry.set_viewport("viewer", west=-180.0, south=-90.0, east=180.0, north=90.0)
    store = _store(clock, registry, maxsize=2)

    for cell in (CALIFORNIA, NSW, ATTICA):
        store.save_state(WorldCellState(cell_id=cell))

    assert store.active_cells == 2, "maxsize outranks attention — memory safety wins"
    assert store.evictions == 1


def test_overflow_prefers_evicting_the_unprotected_cell_over_the_watched_lru_one() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    registry.set_viewport("viewer", **CA_VIEW)  # protects only California
    store = _store(clock, registry, maxsize=2)

    store.save_state(WorldCellState(cell_id=CALIFORNIA))  # LRU, but protected
    store.save_state(WorldCellState(cell_id=NSW))
    store.save_state(WorldCellState(cell_id=ATTICA))  # overflow

    ids = store.active_cell_ids()
    assert CALIFORNIA in ids, "the protected LRU cell is skipped"
    assert NSW not in ids, "the oldest unprotected cell takes the eviction"


def test_stale_viewers_expire_and_stop_protecting() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=60.0, time_fn=clock)
    registry.set_viewport("crashed-client", **CA_VIEW)
    assert registry.protects(CALIFORNIA)

    clock.now = 61.0
    assert not registry.protects(CALIFORNIA)
    assert registry.viewer_count == 0


def test_warming_partition_screens_attended_every_tick_and_everyone_on_cadence() -> None:
    clock = _Clock()
    registry = AttentionRegistry(viewer_ttl_seconds=10_000.0, time_fn=clock)
    registry.set_viewport("viewer", **CA_VIEW)
    registry.set_watchlist("viewer", {ATTICA})
    states = [WorldCellState(cell_id=c) for c in (CALIFORNIA, NSW, ATTICA)]

    off_cadence = {s.cell_id for s in warming_partition(1, states, registry)}
    assert off_cadence == {CALIFORNIA, ATTICA}, "visible + pinned only, between full sweeps"

    on_cadence = {s.cell_id for s in warming_partition(FULL_SWEEP_EVERY, states, registry)}
    assert on_cadence == {CALIFORNIA, NSW, ATTICA}, "full sweep keeps dormant cells honest"
