"""Per-cell drill-down brief — everything the terminal's RegionBriefPanel renders.

One honest read per cell, assembled from what *actually exists* for it today:

- **screening** (Tier 0): the cheap vectorized point estimate per hazard, from the same
  Session-32 sweep the tile server uses. Nearly every cell on the planet has only this.
- **analysis** (Tier 1): the full Monte Carlo + Bayesian forecast — present only when
  the continuous pipeline has genuinely run for this cell (today, the live stream's
  headline cell; Session 38's demand-driven compute widens this).
- **report** (Tier 2): the decision board's intelligence brief, riding the analysis
  when the board convened for it.

The ``tier`` field is the panel's honesty switch: a ``T0`` cell must be presented as a
*screening estimate only* — Session 32 measured the screen biased low by up to ~13 pts
in the mid-risk band — never with the visual weight of a full posterior distribution.
"""

from __future__ import annotations

from typing import Literal

import h3
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from vectis.agents.board.schemas import DecisionIntelligenceReport
from vectis.core.schemas import RiskBand
from vectis.realtime.live_stream import LiveStreamBroadcaster
from vectis.realtime.pipeline import ForecastResult
from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.state.cell_id import DEFAULT_RESOLUTION, parent_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore
from vectis.simulation.schemas import ProbabilityDistribution

router = APIRouter(prefix="/api/v1/cells", tags=["cells"])


class ScenarioBrief(BaseModel):
    """One simulated branch: its posterior weight and full outcome distribution."""

    id: str
    probability: float = Field(description="Posterior weight, 0–1.")
    expected_band: RiskBand
    risk: ProbabilityDistribution


class DriverBrief(BaseModel):
    """One ranked, signed factor behind a T1/T2 cell's risk — the "Why" (Session 41).

    Sourced from the promoted forecast's own coefficients (``HazardModel.explain``); the
    ``caveat`` carries the standing uncalibrated-coefficients honesty label.
    """

    factor: str
    contribution: float = Field(description="Signed log-odds (log-rate for quakes) shift vs baseline.")
    direction: Literal["increases", "decreases", "neutral"]
    input_value: float
    baseline_value: float
    caveat: str


class CellAnalysis(BaseModel):
    """The T1/T2 layer: a real Monte Carlo + Bayesian forecast (and board report)."""

    risk: float
    band: RiskBand
    confidence: float
    posterior: dict[str, float]
    scenarios: list[ScenarioBrief]
    drivers: list[DriverBrief] = Field(
        default_factory=list,
        description="Closed-form driver attribution, ranked by |contribution| — T1/T2 only.",
    )
    report: DecisionIntelligenceReport | None


class CellBrief(BaseModel):
    cell_id: str
    lat: float
    lon: float
    tier: Literal["T0", "T1", "T2"] = Field(
        description="T0 = screened only; T1 = full analysis exists; T2 = board report too."
    )
    state: WorldCellState | None = Field(
        description="The cell's observed variables (None if only the pipeline knows it)."
    )
    screening: dict[str, float] = Field(
        description="Tier-0 per-hazard point estimates, 0–100 — a biased-low approximation."
    )
    source_cells: int = Field(
        default=1,
        description="Native res-5 cells this brief aggregates (1 for a native cell; the "
        "max-per-hazard roll-up of the tile server for coarser map cells).",
    )
    analysis: CellAnalysis | None


def _analysis_view(result: ForecastResult) -> CellAnalysis:
    return CellAnalysis(
        risk=result.risk_score,
        band=result.risk_band,
        confidence=result.confidence,
        posterior=dict(result.posterior),
        scenarios=[
            ScenarioBrief(
                id=o.scenario_id,
                probability=result.posterior.get(o.scenario_id, 0.0),
                expected_band=o.expected_band,
                risk=o.risk,
            )
            for o in result.run.outcomes
        ],
        drivers=[
            DriverBrief(
                factor=d.factor,
                contribution=d.contribution,
                direction=d.direction,
                input_value=d.input_value,
                baseline_value=d.baseline_value,
                caveat=d.caveat,
            )
            for d in result.drivers
        ],
        report=result.report,
    )


def _member_states(
    store: StateStore[WorldCellState], cell_id: str, resolution: int
) -> list[WorldCellState]:
    """The native res-5 states a map cell at any H3 resolution stands for.

    Native → the cell itself. Coarser (map roll-up) → every active native cell under
    it. Finer (display subdivision) → the native parent the subdivision inherited its
    score from. Mirrors the tile server's re-gridding, so a click on any rendered cell
    resolves to the same underlying data the tile was painted with.
    """
    if resolution == DEFAULT_RESOLUTION:
        state = store.get_state(cell_id)
        return [state] if state is not None else []
    if resolution < DEFAULT_RESOLUTION:
        return [
            s for s in store.active_states()
            if parent_cell_id(s.cell_id, resolution) == cell_id
        ]
    parent = store.get_state(parent_cell_id(cell_id, DEFAULT_RESOLUTION))
    return [parent] if parent is not None else []


@router.get("/{cell_id}/brief", response_model=CellBrief)
def cell_brief(cell_id: str, request: Request) -> CellBrief:
    """The drill-down brief for one H3 cell — screening always, deep analysis only if real."""
    if not h3.is_valid_cell(cell_id):
        raise HTTPException(status_code=404, detail=f"{cell_id!r} is not a valid H3 cell id")

    store: StateStore[WorldCellState] = request.app.state.tile_store
    members = _member_states(store, cell_id, h3.get_resolution(cell_id))
    # Max per hazard across members — the tile server's roll-up rule (a hot native
    # cell must never be averaged away by its siblings under a coarse map cell).
    screening: dict[str, float] = {}
    for scores in GlobalScreeningSweep().sweep(members).values():
        for hazard, score in scores.items():
            screening[hazard] = max(screening.get(hazard, 0.0), score.value)
    # The observed-state panel only makes sense for exactly one underlying cell.
    state = members[0] if len(members) == 1 else None

    # T1/T2 forecasts now come from the shared compute loop (Session 38) first — the
    # tiering engine's demand-driven results — with the legacy single-cell live
    # pipeline as fallback so /live's headline cell keeps its brief.
    live: LiveStreamBroadcaster = request.app.state.live_stream
    compute = getattr(request.app.state, "compute", None)
    result: ForecastResult | None = (
        compute.results.get(cell_id) if compute is not None else None
    ) or live.pipeline.results.get(cell_id)
    if not members and result is None:
        raise HTTPException(status_code=404, detail=f"no observed state for cell {cell_id!r}")

    analysis = _analysis_view(result) if result is not None else None
    tier: Literal["T0", "T1", "T2"] = (
        "T2" if analysis is not None and analysis.report is not None
        else "T1" if analysis is not None
        else "T0"
    )
    lat, lon = h3.cell_to_latlng(cell_id)
    return CellBrief(
        cell_id=cell_id, lat=lat, lon=lon, tier=tier,
        state=state, screening=screening, source_cells=max(len(members), 1),
        analysis=analysis,
    )
