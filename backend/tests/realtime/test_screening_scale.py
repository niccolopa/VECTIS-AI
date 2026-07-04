"""Session 32 — the screening speed proof.

The Tier 0 promise: score **every** active cell on every update at essentially zero cost, so
the global heat map can light up the whole active world without ever running the heavy
engine. This test builds ~100k active cells with plausible wildfire state and asserts the
full screening sweep stays cheap, single-threaded — measuring and printing the real
number in the spirit of ``make stress``, not assuming a speedup.

The assertion is a generous *sanity ceiling*, not a benchmark: the printed number is
the real measurement (typically ~0.4–0.6s on a dev laptop). GC is excluded from the
timed region so the result reflects screening cost, not allocator state — without that,
running inside the full suite (heap full of prior-test objects) triggered mid-sweep GC
pauses that pushed the wall-clock ~2.5x higher and flaked CI (which runs slow tests with
``--maxfail=1``). The ceiling keeps headroom for slower CI runners on top of that.

Marked ``slow`` (a scale proof, not needed on every push: ``pytest -m "not slow"``).
"""

from __future__ import annotations

import gc
import random
import time

import pytest

# Reuse Session 30's land-weighted point generator rather than duplicating the bboxes
# (sibling module, same tests/realtime dir — importable under pytest's prepend import mode).
from test_global_grid_scale import _random_land_point

from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.state.cell_id import assign_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore

_CELLS = 100_000
# Contention-tolerant ceiling (see module docstring). Isolated runs are ~0.4–0.6s;
# this leaves ~3–4x headroom for slow/loaded CI runners so the scale proof never
# flakes a green build. The printed cells/s is the honest number to read.
_BUDGET_SECONDS = 2.0


def _plausible_cell(rng: random.Random, cell_id: str) -> WorldCellState:
    """A cell with realistic wildfire-relevant state: a temperature and a wind reading."""
    return WorldCellState(
        cell_id=cell_id,
        temperature=rng.uniform(8.0, 44.0),
        extra={"wind_speed_kmh": rng.uniform(0.0, 80.0)},
    )


@pytest.mark.slow
def test_screening_sweeps_100k_active_cells_stays_cheap() -> None:
    rng = random.Random(32)
    # ~100k active cells landed on real H3 cells at land-weighted coordinates (Session 30
    # generator). Land points collide onto shared res-5 cells, so we keep sampling until the
    # hot set reaches the target — the honest "active set", populated the way ingestion does.
    store: EvictingStateStore[WorldCellState] = EvictingStateStore(
        MemoryStateStore(), maxsize=_CELLS + 20_000
    )
    attempts = 0
    while store.active_cells < _CELLS and attempts < 10 * _CELLS:
        lat, lon = _random_land_point(rng)
        store.save_state(_plausible_cell(rng, assign_cell_id(lat, lon)))
        attempts += 1

    active = store.active_cells
    assert active >= _CELLS, f"expected ~{_CELLS} active cells, got {active}"

    sweep = GlobalScreeningSweep()
    # Exclude GC from the measurement: a full heap from prior tests otherwise triggers
    # mid-sweep collection pauses that measure the allocator, not the screening cost.
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter()
        result = sweep.sweep_store(store)
        elapsed = time.perf_counter() - start
    finally:
        gc.enable()

    print(f"\nscreened {active} active cells in {elapsed * 1000:.1f} ms "
          f"({active / elapsed:,.0f} cells/s, single-threaded)")

    assert len(result) == active, "every active wildfire cell must get a score"
    assert all("wildfire" in scores for scores in result.values())
    assert elapsed < _BUDGET_SECONDS, f"screening sweep took {elapsed:.3f}s (budget {_BUDGET_SECONDS}s)"
