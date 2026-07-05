"""Session 38 — the shared compute pipeline: real T1/T2 for arbitrary global cells.

One loop owns ingest → screen → tier → Monte Carlo → board; SSE connections are
fan-out queues. Offline and deterministic: no network, the default mock LLM narrates.
Reminder: every number here rides illustrative, uncalibrated coefficients.
"""

from __future__ import annotations

import h3

from vectis.agents.board.service import SimulationBoardService
from vectis.realtime.attention import AttentionRegistry
from vectis.realtime.compute import CellForecastRunner, SharedComputeLoop
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.screening.multi_hazard import FloodScreeningIndex
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.tiering.manager import TierManager
from vectis.simulation.schemas import SimulationConfig

WET = h3.latlng_to_cell(22.5, 90.0, 5)  # a deluge cell (Bengal delta-ish)
DAMP = h3.latlng_to_cell(48.0, 11.0, 5)  # a drizzle cell nobody watches
SHAKEN = h3.latlng_to_cell(38.3, 142.4, 5)  # a fresh mainshock cell

_FAST = SimulationConfig(n_iterations=1500, seed=38, parallel=False, n_workers=1)


def _wet_state(cell_id: str = WET) -> WorldCellState:
    return WorldCellState(cell_id=cell_id, precipitation_mm=90.0, flood_alert_level=3.0)


def _loop(
    store: MemoryStateStore[WorldCellState],
    *,
    attention: AttentionRegistry | None = None,
    tier: TierManager | None = None,
) -> SharedComputeLoop:
    """A fully-offline loop: no connectors, fast Monte Carlo, mock-LLM board."""
    return SharedComputeLoop(
        store=store,
        attention=attention or AttentionRegistry(),
        ingestion=GlobalIngestionBroadcaster(store, manager=IngestionManager([])),
        tier=tier,
        runner=CellForecastRunner(config=_FAST),
        board=SimulationBoardService(),
    )


# ── the real T1 runner ──────────────────────────────────────────────────────────────
def test_runner_attaches_closed_form_drivers_to_the_real_forecast() -> None:
    """A genuinely-promoted T1 forecast carries its driver attribution, computed from the
    cell's observed drivers vs the illustrative twin baseline — flood's own factors,
    ranked, honestly labeled. Only real forecasts get this; nothing forces promotion."""
    runner = CellForecastRunner(config=_FAST)
    wet, _ = runner.forecast(_wet_state(), "flood")

    assert wet.drivers, "a promoted forecast must expose its drivers"
    factors = {d.factor for d in wet.drivers}
    assert factors <= {"precipitation_mm", "flood_alert_level"}
    # A wet, high-alert cell above the baseline twin → drivers push risk up.
    assert any(d.direction == "increases" for d in wet.drivers)
    # Ranked by |contribution|, and every driver honestly caveated.
    mags = [abs(d.contribution) for d in wet.drivers]
    assert mags == sorted(mags, reverse=True)
    assert all(d.caveat for d in wet.drivers)


def test_runner_forecasts_a_flood_cell_from_its_observed_state() -> None:
    runner = CellForecastRunner(config=_FAST)
    wet, board_input = runner.forecast(_wet_state(), "flood")
    damp, _ = runner.forecast(
        WorldCellState(cell_id=DAMP, precipitation_mm=5.0, flood_alert_level=1.0), "flood"
    )

    assert wet.cell_id == WET
    assert 0.0 <= wet.risk_score <= 100.0
    assert abs(sum(wet.posterior.values()) - 1.0) < 1e-9
    # The observed drivers are projected over the twin baseline, so the deluge cell
    # must simulate materially worse than the drizzle cell — direction, not calibration.
    assert wet.risk_score > damp.risk_score + 10.0
    assert wet.run.outcomes, "a real Monte Carlo run backs the headline"
    assert board_input.risk_score == wet.risk_score
    assert board_input.scenarios, "the board narrates the engine's scenarios, per firewall"


def test_runner_handles_every_seamed_hazard() -> None:
    runner = CellForecastRunner(config=_FAST)
    states = {
        "wildfire": WorldCellState(
            cell_id=WET, temperature=38.0, extra={"wind_speed_kmh": 45.0}
        ),
        "flood": _wet_state(),
        "quake": WorldCellState(cell_id=SHAKEN, earthquake_magnitude=7.1),
        "cyclone": WorldCellState(
            cell_id=SHAKEN, cyclone_alert_level=3.0, extra={"wind_speed_kmh": 150.0}
        ),
    }
    for hazard, state in states.items():
        result, _ = runner.forecast(state, hazard)
        assert 0.0 <= result.risk_score <= 100.0, hazard
        assert 0.0 <= result.confidence <= 1.0, hazard


# ── the shared loop ─────────────────────────────────────────────────────────────────
def test_pinned_cell_flows_t0_to_t1_to_t2_through_one_cycle() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    # Mild enough that no screening gate can fire (guard below) — only the pin promotes.
    state = WorldCellState(cell_id=WET, precipitation_mm=20.0, flood_alert_level=1.0)
    assert FloodScreeningIndex().score([state])[WET].value < 85.0
    store.save_state(state)
    attention = AttentionRegistry()
    attention.set_watchlist("operator", {WET})
    loop = _loop(store, attention=attention)

    loop.run_cycle()

    result = loop.results[WET]
    assert result.risk_score > 0.0
    assert result.report is not None, "first forecast is material → the pin narrates (T2)"
    assert loop.forecasts_run == 1 and loop.reports_generated == 1
    assert loop.last_cycle is not None
    assert loop.last_cycle.t1_batch[0].reason == "watchlist_refresh"


def test_hot_unpinned_cell_promotes_on_its_own_screen_score() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    state = _wet_state()
    store.save_state(state)
    # Self-calibrating threshold: whatever the screen reads for this cell, set the
    # cutoff just below it so the score gate (not the pin) drives the promotion.
    score = FloodScreeningIndex().score([state])[WET].value
    loop = _loop(store, tier=TierManager(t1_score_cutoff=score - 1.0))

    loop.run_cycle()

    assert WET in loop.results
    assert loop.last_cycle is not None
    assert loop.last_cycle.t1_batch[0].reason == "score_threshold"


def test_dormant_unwatched_cells_cost_zero_expensive_compute() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    store.save_state(WorldCellState(cell_id=DAMP, precipitation_mm=3.0))
    loop = _loop(store)

    for _ in range(3):
        loop.run_cycle()

    assert loop.forecasts_run == 0, "no attention + no event → screening only, ever"
    assert loop.results == {}
    assert loop.latest_scores.get(DAMP), "…but the cheap screen still tracks it honestly"


def test_evicted_cells_drop_out_of_shared_results() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    store.save_state(_wet_state())
    attention = AttentionRegistry()
    attention.set_watchlist("operator", {WET})
    loop = _loop(store, attention=attention)
    loop.run_cycle()
    assert WET in loop.results

    store.delete(WET)  # eviction is a real delete (Session 30)
    loop.run_cycle()

    assert WET not in loop.results, "a forecast must not outlive its cell's state"
    assert WET not in loop.latest_scores
