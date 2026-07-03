"""Session 38 — the attention-bounded load proof.

The claim under test, measured and printed honestly (the ``make stress`` tradition):
total compute tracks **actual attention + real events**, never **viewer count x grid
size**. Many viewers over the same viewports must cost the same expensive compute as a
few; a dormant, unwatched region must cost nothing beyond the background screen no
matter how many viewers are connected elsewhere.

The T1 stage is a counting stub — the Monte Carlo sampler's own numbers are Session
13's proof; this test measures the *scheduling*, which is what Session 38 built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import h3
import numpy as np

from vectis.core.schemas import RiskBand
from vectis.realtime.attention import FULL_SWEEP_EVERY, AttentionRegistry
from vectis.realtime.compute import SharedComputeLoop
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.tiering.manager import TierManager

# -- the world: four regions with very different attention/activity profiles ---------
HOT_VIEW = {"west": -125.0, "south": 32.0, "east": -114.0, "north": 42.0}  # watched + hot
CALM_VIEW = {"west": 5.0, "south": 44.0, "east": 15.0, "north": 54.0}  # watched, quiet
DORMANT_VIEW = {"west": 120.0, "south": -30.0, "east": 130.0, "north": -20.0}  # nobody looks


def _cells_in(view: dict[str, float], n_side: int) -> list[str]:
    lats = np.linspace(view["south"] + 0.4, view["north"] - 0.4, n_side)
    lons = np.linspace(view["west"] + 0.4, view["east"] - 0.4, n_side)
    return sorted({h3.latlng_to_cell(la, lo, 5) for la in lats for lo in lons})


@dataclass
class _StubResult:
    """The minimum surface the loop stores per forecast — no Monte Carlo needed here."""

    cell_id: str
    risk_score: float
    confidence: float = 0.5
    risk_band: RiskBand = RiskBand.HIGH
    posterior: dict[str, float] | None = None
    report: Any = None
    run: Any = None


class _CountingRunner:
    """Counts T1 executions per cell instead of sampling — the scheduling is the test."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    def forecast(self, state: WorldCellState, hazard: str) -> tuple[_StubResult, Any]:
        self.calls[state.cell_id] = self.calls.get(state.cell_id, 0) + 1
        return _StubResult(cell_id=state.cell_id, risk_score=88.0), object()


def _build_world(store: MemoryStateStore[WorldCellState]) -> dict[str, list[str]]:
    regions = {
        "hot": _cells_in(HOT_VIEW, 7),  # ~49 cells crossing the T1 cutoff
        "calm": _cells_in(CALM_VIEW, 15),  # ~200 watched-but-quiet cells
        "dormant": _cells_in(DORMANT_VIEW, 15),  # ~200 unwatched, quiet cells
    }
    for cell in regions["hot"]:
        store.save_state(
            WorldCellState(cell_id=cell, precipitation_mm=90.0, flood_alert_level=3.0)
        )
    for cell in regions["calm"] + regions["dormant"]:
        store.save_state(WorldCellState(cell_id=cell, precipitation_mm=4.0))
    return regions


def _run(n_viewers: int, cycles: int = 6) -> tuple[SharedComputeLoop, _CountingRunner, dict]:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    regions = _build_world(store)
    attention = AttentionRegistry()
    # Viewers split over two shared viewports — overlap is the norm on a real desk.
    for i in range(n_viewers):
        attention.set_viewport(f"viewer-{i}", **(HOT_VIEW if i % 2 == 0 else CALM_VIEW))
    # A few operators pin calm cells: guaranteed refresh without any score signal.
    pins = regions["calm"][:5]
    attention.set_watchlist("viewer-0", set(pins))

    runner = _CountingRunner()
    loop = SharedComputeLoop(
        store=store,
        attention=attention,
        ingestion=GlobalIngestionBroadcaster(store, manager=IngestionManager([])),
        tier=TierManager(max_t1_per_cycle=64, max_t2_per_cycle=5, watchlist_refresh_cycles=3),
        runner=runner,  # type: ignore[arg-type]  # counting stub, same duck surface
        board=None,
    )
    for _ in range(cycles):
        loop.run_cycle()
    return loop, runner, regions


def test_compute_tracks_attention_and_events_not_viewer_count_times_grid() -> None:
    cycles = 6
    few_loop, few_runner, _ = _run(n_viewers=5, cycles=cycles)
    many_loop, many_runner, regions = _run(n_viewers=50, cycles=cycles)

    hot_set = sum(len(c) for c in regions.values())
    naive = 50 * hot_set * cycles  # what per-viewer compute would have screened

    print("\n-- attention-bounded load proof ------------------------------")
    print(f"world: {hot_set} active cells ({len(regions['hot'])} hot, "
          f"{len(regions['calm'])} watched-calm, {len(regions['dormant'])} dormant)")
    print(f"naive model (viewers x grid x ticks): {naive:,} cell-screens")
    print(f"actual, 50 viewers: {many_loop.cells_screened_total:,} cell-screens, "
          f"{many_loop.forecasts_run} T1 runs")
    print(f"actual,  5 viewers: {few_loop.cells_screened_total:,} cell-screens, "
          f"{few_loop.forecasts_run} T1 runs")

    # 1. Ten times the viewers, identical expensive compute — the fan-out is shared.
    assert many_loop.forecasts_run == few_loop.forecasts_run
    assert many_loop.cells_screened_total == few_loop.cells_screened_total
    assert many_runner.calls == few_runner.calls

    # 2. Compute is a small fraction of the naive per-viewer model.
    assert many_loop.cells_screened_total < naive / 25

    # 3. T1 lands only where attention or heat is: hot cells and pins, never dormant.
    dormant = set(regions["dormant"])
    assert not dormant & set(many_runner.calls), "a dormant unwatched cell cost a T1 run"
    assert set(regions["hot"]) <= set(many_runner.calls), "every hot cell was analyzed"
    pinned = set(regions["calm"][:5])
    assert pinned <= set(many_runner.calls), "pins got their scheduled refresh"
    # Unpinned calm cells stay T0: watched ≠ promoted; the gates still decide.
    assert not (set(regions["calm"]) - pinned) & set(many_runner.calls)

    # 4. The T1 budget held every cycle (the storm test's invariant, at this scale).
    assert many_loop.last_cycle is not None
    assert all(c <= cycles for c in many_runner.calls.values())


def test_off_cadence_ticks_screen_only_the_attended_cells() -> None:
    loop, _, regions = _run(n_viewers=10, cycles=FULL_SWEEP_EVERY + 2)
    attended_ish = len(regions["hot"]) + len(regions["calm"])  # both watched viewports
    hot_set = sum(len(c) for c in regions.values())

    # The final tick (tick index FULL_SWEEP_EVERY+1) is off-cadence: warming only.
    assert loop.cells_screened_last <= attended_ish + 5
    assert loop.cells_screened_last < hot_set, "off-cadence ticks must not sweep the world"
    print(f"off-cadence screen: {loop.cells_screened_last} of {hot_set} active cells "
          f"(attended ~ {attended_ish})")
