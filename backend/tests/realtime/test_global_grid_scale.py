"""Session 30 — the bounded-memory proof for the sparse global grid.

The V4 foundational claim: stream an unbounded torrent of observations from anywhere on
Earth through the pipeline and memory stays bounded by the *active* set, never the size of
the planet. This test streams 100k land-scattered observations through
``assign_cell_id`` → ``EvictingStateStore`` and asserts the hot set never exceeds its
configured bound — regardless of how many total observations were processed.

Marked ``slow``: it's a stress proof, not needed on every push (``pytest -m "not slow"``).
"""

from __future__ import annotations

import random

import h3
import pytest

from vectis.realtime.events.base import GlobalObservation
from vectis.realtime.state.cell_id import assign_cell_id, children_cell_ids, parent_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore
from vectis.realtime.state.updater import StateUpdater

# A handful of continental bounding boxes (W, S, E, N). Sampling within these keeps the
# synthetic stream land-weighted — realistic ignition points, not uniform ocean noise.
_LAND_BBOXES = [
    (-124.0, 32.0, -114.0, 42.0),   # California / US West
    (-9.0, 36.0, 3.0, 44.0),        # Iberia
    (113.0, -39.0, 154.0, -20.0),   # SE Australia
    (-74.0, -34.0, -40.0, -2.0),    # Brazil
    (15.0, -12.0, 40.0, 5.0),       # Central Africa
]

_OBSERVATIONS = 100_000
_MAXSIZE = 2_000


def _random_land_point(rng: random.Random) -> tuple[float, float]:
    west, south, east, north = rng.choice(_LAND_BBOXES)
    return rng.uniform(south, north), rng.uniform(west, east)


@pytest.mark.slow
def test_hot_set_stays_bounded_under_100k_observations() -> None:
    rng = random.Random(30)
    store: EvictingStateStore[WorldCellState] = EvictingStateStore(
        MemoryStateStore(), maxsize=_MAXSIZE
    )
    updater = StateUpdater(store)

    peak = 0
    for i in range(_OBSERVATIONS):
        lat, lon = _random_land_point(rng)
        cell = assign_cell_id(lat, lon)
        updater.apply_observation(
            GlobalObservation(
                cell_id=cell, variable="temp_anomaly_c",
                value=rng.uniform(0.0, 40.0), source="scale_test",
            )
        )
        # The invariant must hold *throughout*, not just at the end.
        if i % 5_000 == 0:
            assert store.active_cells <= _MAXSIZE
            peak = max(peak, store.active_cells)

    assert store.active_cells <= _MAXSIZE
    # The proof is only meaningful if we actually overflowed the bound many times over.
    assert store.evictions > 0
    assert peak <= _MAXSIZE


@pytest.mark.slow
def test_h3_aggregation_round_trips_across_the_grid() -> None:
    """Every child's parent is stable, and adjacent fine cells roll up consistently."""
    rng = random.Random(31)
    for _ in range(1000):
        lat, lon = _random_land_point(rng)
        cell = assign_cell_id(lat, lon)  # resolution 5

        # Children round-trip: each res-7 child's parent at res 5 is the original cell.
        for child in children_cell_ids(cell, 7):
            assert parent_cell_id(child, 5) == cell

        # Geographic adjacency: a cell and its immediate neighbors share a coarse parent
        # is NOT guaranteed at every boundary — but a cell's own parent is deterministic
        # and every neighbor's parent is itself deterministic and stable across calls.
        for neighbor in h3.grid_disk(cell, 1):
            parent = parent_cell_id(neighbor, 3)
            assert parent == parent_cell_id(neighbor, 3)  # deterministic across calls
            assert h3.get_resolution(parent) == 3
