"""Session 37 — the per-cell drill-down brief.

The brief must be honest about what exists for a cell: a screened-only cell is T0
(screening scores, no analysis object), a cell the continuous pipeline has genuinely
forecast is T1 (full distributions + posterior), and T2 only when a board report rides
the forecast. Nothing is fabricated to make a panel look fuller.
"""

from __future__ import annotations

from vectis.core.schemas import RiskBand
from vectis.realtime.pipeline import ForecastResult
from vectis.realtime.state.cell_id import assign_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.simulation.models.base import Driver
from vectis.simulation.schemas import (
    ProbabilityDistribution,
    ScenarioOutcome,
    SimulationConfig,
    SimulationRun,
)

_HOT = (37.0, -120.0)


def _hot_cell() -> WorldCellState:
    return WorldCellState(
        cell_id=assign_cell_id(*_HOT),
        temperature=40.0,
        flood_alert_level=3.0,
        precipitation_mm=95.0,
        extra={"wind_speed_kmh": 60.0},
    )


def _forecast(cell_id: str) -> ForecastResult:
    dist = ProbabilityDistribution(
        variable="risk_score", mean=68.0, std=9.0, p05=51.0, p50=68.0, p95=84.0,
        exceedance={"high": 0.8},
    )
    run = SimulationRun(
        run_id="run-test", region="california",
        config=SimulationConfig(n_iterations=100, seed=1),
        outcomes=[ScenarioOutcome(scenario_id="baseline", risk=dist)],
    )
    return ForecastResult(
        cell_id=cell_id, risk_score=68.0, confidence=0.82,
        risk_band=RiskBand.from_score(68.0),
        posterior={"baseline": 1.0}, run=run,
        drivers=[
            Driver("temp_anomaly_c", contribution=1.65, input_value=18.0, baseline_value=15.0),
            Driver("wind_speed_kmh", contribution=-0.4, input_value=10.0, baseline_value=30.0),
        ],
    )


def test_screened_only_cell_is_an_honest_t0(client) -> None:
    cell = _hot_cell()
    client.app.state.tile_store.save_state(cell)

    res = client.get(f"/api/v1/cells/{cell.cell_id}/brief")
    assert res.status_code == 200
    body = res.json()

    assert body["tier"] == "T0"
    assert body["analysis"] is None  # nothing deep exists — nothing deep is shown, no drivers
    assert body["screening"]["wildfire"] > 0
    assert body["screening"]["flood"] > 50.0
    assert body["state"]["temperature"] == 40.0


def test_pipeline_forecast_cell_is_t1_with_full_distributions(client) -> None:
    cell = _hot_cell()
    client.app.state.tile_store.save_state(cell)
    client.app.state.live_stream.pipeline.results[cell.cell_id] = _forecast(cell.cell_id)

    body = client.get(f"/api/v1/cells/{cell.cell_id}/brief").json()

    assert body["tier"] == "T1"  # analysis, no board report yet
    analysis = body["analysis"]
    assert analysis["risk"] == 68.0
    assert analysis["posterior"] == {"baseline": 1.0}
    scenario = analysis["scenarios"][0]
    assert scenario["id"] == "baseline"
    assert (scenario["risk"]["p05"], scenario["risk"]["p50"], scenario["risk"]["p95"]) == (
        51.0, 68.0, 84.0,
    )
    # Screening rides along — the panel can show the gap between screen and engine.
    assert body["screening"]["wildfire"] > 0
    # The "Why" drivers ride the real analysis — ranked, signed, honestly labeled.
    drivers = analysis["drivers"]
    assert [d["factor"] for d in drivers] == ["temp_anomaly_c", "wind_speed_kmh"]
    assert drivers[0]["direction"] == "increases" and drivers[1]["direction"] == "decreases"
    assert all(d["caveat"] for d in drivers)


def test_unknown_or_invalid_cells_404(client) -> None:
    assert client.get("/api/v1/cells/not-a-cell/brief").status_code == 404
    never_observed = assign_cell_id(-45.0, 170.0)  # a valid cell nothing has touched
    assert client.get(f"/api/v1/cells/{never_observed}/brief").status_code == 404
