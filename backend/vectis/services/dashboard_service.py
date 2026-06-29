"""Dashboard service — view-models the V2 frontend consumes.

Composes the existing layers (Digital Twin · Monte Carlo engine · S13 cache · LLM
board) into payloads shaped for **enterprise visualization**: not a single "94%",
but per-scenario :class:`ProbabilityDistribution`s (mean/std/p05/p50/p95 +
exceedance) so the UI can draw box-and-whisker / confidence-fan charts, plus the
aggregate :class:`RiskState` and the AI :class:`DecisionIntelligenceReport`.

Two operations back the dashboard:
- :meth:`twin_view` — everything about a twin's *current* state (GET).
- :meth:`what_if` — recompute risk for a *user-modified* state (POST), routed
  through the memoizing engine so identical sliders return instantly.

All math comes from the engine; this layer only reshapes it (no LLM in the numbers).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from vectis.agents.board.schemas import DecisionIntelligenceReport
from vectis.agents.board.service import SimulationBoardService
from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.digital_twin.entities.region import (
    RegionState,
    RegionTwin,
    region_to_world_state,
)
from vectis.digital_twin.schemas import RiskState
from vectis.digital_twin.state.manager import StateManager
from vectis.simulation.caching import MemoizingMonteCarloEngine
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.probability.uncertainty import (
    posterior_mixture_risk,
    scenario_confidence,
)
from vectis.simulation.schemas import (
    ProbabilityDistribution,
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
)

log = get_logger(__name__)


# ── View-models (frontend contracts) ─────────────────────────────────────────
class ScenarioProjection(BaseModel):
    """One scenario branch with its full outcome distribution — the unit a
    Scenario Explorer renders as a box-and-whisker / fan per branch."""

    id: str
    name: str
    description: str
    probability: float = Field(ge=0.0, le=1.0, description="Posterior weight of this branch.")
    expected_band: RiskBand
    risk: ProbabilityDistribution


class TwinDashboardView(BaseModel):
    """Everything the dashboard needs for one twin's current posture."""

    twin_id: str
    kind: str
    state: RegionState
    risk: RiskState
    scenarios: list[ScenarioProjection]
    report: DecisionIntelligenceReport


class StateOverrides(BaseModel):
    """User-supplied What-If deltas; any omitted field keeps the twin's value."""

    temperature_anomaly: float | None = None
    humidity_level: float | None = None
    vegetation_stress: float | None = None
    recent_fire_history: float | None = None


class WhatIfRequest(BaseModel):
    twin_id: str = "liguria"
    overrides: StateOverrides = Field(default_factory=StateOverrides)
    n_iterations: int | None = Field(default=None, ge=1, description="Override MC iterations.")


class WhatIfResult(BaseModel):
    """The recomputed posture for a hypothetical (user-modified) state."""

    twin_id: str
    state: RegionState
    risk: RiskState
    scenarios: list[ScenarioProjection]


# ── Service ──────────────────────────────────────────────────────────────────
class DashboardService:
    """Builds dashboard view-models from the live twin registry + engines."""

    def __init__(
        self,
        manager: StateManager,
        *,
        engine: MemoizingMonteCarloEngine | None = None,
        board: SimulationBoardService | None = None,
        config: SimulationConfig | None = None,
    ) -> None:
        self._manager = manager
        # Memoizing engine (S13): identical (state, scenarios, config) → instant.
        self._engine = engine or MemoizingMonteCarloEngine(VectorizedMonteCarloEngine())
        self._board = board or SimulationBoardService()
        self._config = config or SimulationConfig(n_iterations=20_000, seed=7)

    def list_twins(self) -> list[str]:
        return [t.twin_id for t in self._manager.all() if isinstance(t, RegionTwin)]

    def twin_view(self, twin_id: str) -> TwinDashboardView | None:
        twin = self._manager.get(twin_id)
        if not isinstance(twin, RegionTwin):
            return None
        state = twin.get_current_state()
        risk, scenarios = self._project(twin, state, self._config)
        report = self._board.analyze_twin(twin)
        return TwinDashboardView(
            twin_id=twin.twin_id, kind=twin.kind, state=state,
            risk=risk, scenarios=scenarios, report=report,
        )

    def what_if(self, request: WhatIfRequest) -> WhatIfResult | None:
        twin = self._manager.get(request.twin_id)
        if not isinstance(twin, RegionTwin):
            return None
        # Merge user deltas onto the twin's current state (omitted fields kept).
        deltas = request.overrides.model_dump(exclude_none=True)
        state = twin.get_current_state().model_copy(update=deltas)
        config = (
            self._config.model_copy(update={"n_iterations": request.n_iterations})
            if request.n_iterations
            else self._config
        )
        risk, scenarios = self._project(twin, state, config)
        log.info(
            "dashboard.what_if", twin_id=twin.twin_id, overrides=deltas,
            risk=round(risk.risk, 1), cache_hits=self._engine.cache.hits,
        )
        return WhatIfResult(twin_id=twin.twin_id, state=state, risk=risk, scenarios=scenarios)

    # ── internals ────────────────────────────────────────────────────────────
    def _project(
        self, twin: RegionTwin, state: RegionState, config: SimulationConfig
    ) -> tuple[RiskState, list[ScenarioProjection]]:
        """Run (cached) Monte Carlo for ``state`` under the twin's current beliefs
        and reshape into an aggregate :class:`RiskState` + per-branch projections."""
        world = region_to_world_state(twin.twin_id, state)
        run = self._engine.run(world, twin.scenarios, config)
        return (
            self._risk_state(twin.twin_id, twin.scenarios, run),
            self._projections(twin.scenarios, run),
        )

    @staticmethod
    def _risk_state(twin_id: str, scenarios: ScenarioSet, run: SimulationRun) -> RiskState:
        means = {o.scenario_id: o.risk.mean for o in run.outcomes}
        risk = posterior_mixture_risk(scenarios, means)
        return RiskState(
            region=twin_id,
            risk=risk,
            band=RiskBand.from_score(risk),
            confidence=scenario_confidence(scenarios),
            scenario_priors={s.id: s.prior for s in scenarios.scenarios},
        )

    @staticmethod
    def _projections(scenarios: ScenarioSet, run: SimulationRun) -> list[ScenarioProjection]:
        outcomes = {o.scenario_id: o for o in run.outcomes}
        projections: list[ScenarioProjection] = []
        for s in scenarios.scenarios:
            o = outcomes[s.id]
            projections.append(
                ScenarioProjection(
                    id=s.id, name=s.name, description=s.description,
                    probability=s.prior, expected_band=o.expected_band, risk=o.risk,
                )
            )
        return projections
