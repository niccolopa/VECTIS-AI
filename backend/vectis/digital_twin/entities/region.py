"""Climate Risk Twin — the first concrete :class:`DigitalTwin`.

A :class:`RegionTwin` is a living model of a geographic area's wildfire risk. It
holds the region's **physical state** (temperature anomaly, humidity, vegetation
stress, recent fire history), evolves that state deterministically as observations
arrive, and drives the V2 probability engines to keep a **computed risk state**
current.

The twin is the *business logic*; the Monte Carlo engine and Bayesian updater are
generic *calculators* it composes. The twin's only engine-specific knowledge is
:meth:`_to_world_state` — the mapping from its domain fields onto the engine's
``WorldState`` variables. Swap that mapping (and the transition + scenarios) and the
same machinery models something else entirely.
"""

from __future__ import annotations

import threading

from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.digital_twin.entities.base import DigitalTwin, TwinState
from vectis.digital_twin.schemas import RiskState, TwinUpdate
from vectis.digital_twin.transitions.base import ClimateTransition, StateTransition
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.probability.bayesian import GaussianBayesianUpdater, Observation
from vectis.simulation.probability.uncertainty import (
    posterior_mixture_risk,
    scenario_confidence,
)
from vectis.simulation.scenarios.generator import WildfireScenarioGenerator
from vectis.simulation.schemas import (
    DistributionFamily,
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    StateVariable,
    WorldState,
)

log = get_logger(__name__)

#: Wind isn't a twin state field; the engine still needs it for the extreme-wind
#: scenario, so the twin carries a fixed baseline. ponytail: constant until a wind
#: feed exists.
_WIND_BASELINE_KMH = 35.0


def _total_variation(prior: ScenarioSet, posterior: ScenarioSet) -> float:
    """TV distance between two beliefs over the same scenarios: ½·Σ|Δprior|."""
    post = {s.id: s.prior for s in posterior.scenarios}
    return 0.5 * sum(abs(s.prior - post.get(s.id, 0.0)) for s in prior.scenarios)


def region_to_world_state(twin_id: str, state: RegionState) -> WorldState:
    """Map a region's domain state onto the engine's ``WorldState`` variables.

    This is the *only* engine-specific knowledge in the region twin, factored to a
    module function so callers that need to simulate an *arbitrary* state (e.g. the
    dashboard what-if endpoint sliding temperature to +5 °C) can reuse the exact same
    mapping the twin uses internally. Vegetation stress and recent fires raise the
    ignition rate; low humidity becomes a negative rainfall anomaly. Uncertainties
    mirror the Session-7 Liguria twin.
    """
    rainfall_anomaly = state.humidity_level - 50.0
    ignition = max(
        0.0, 1.5 + state.recent_fire_history * 0.5 + (state.vegetation_stress - 50.0) * 0.02
    )
    return WorldState(
        region=twin_id,
        variables=[
            StateVariable(
                name="temp_anomaly_c", value=state.temperature_anomaly,
                family=DistributionFamily.NORMAL, std=0.5, unit="°C",
            ),
            StateVariable(
                name="rainfall_anomaly_pct", value=rainfall_anomaly,
                family=DistributionFamily.NORMAL, std=8.0, unit="%",
            ),
            StateVariable(
                name="wind_speed_kmh", value=_WIND_BASELINE_KMH,
                family=DistributionFamily.LOGNORMAL, std=0.25, unit="km/h",
            ),
            StateVariable(
                name="ignition_sources", value=ignition,
                family=DistributionFamily.POISSON, unit="count/day",
            ),
        ],
    )


class RegionState(TwinState):
    """The physical state of a region twin.

    Defaults reproduce the Session-7 Liguria digital twin exactly once mapped
    through :meth:`RegionTwin._to_world_state` (temp +2 °C, 20 % humidity → −30 %
    rainfall anomaly, baseline vegetation stress, no recent fires).
    """

    temperature_anomaly: float = 2.0  # °C above seasonal baseline
    humidity_level: float = 20.0  # %
    vegetation_stress: float = 50.0  # 0–100 dryness/fuel-stress index
    recent_fire_history: float = 0.0  # count of recent active-fire detections


class RegionTwin(DigitalTwin):
    """A self-updating wildfire-risk twin for one geographic region."""

    kind = "region"

    def __init__(
        self,
        twin_id: str = "liguria",
        *,
        state: RegionState | None = None,
        scenarios: ScenarioSet | None = None,
        engine: VectorizedMonteCarloEngine | None = None,
        config: SimulationConfig | None = None,
        transition: StateTransition | None = None,
        model_std: float = 1.0,
        rerun_threshold: float = 0.02,
    ) -> None:
        self.twin_id = twin_id
        self._state = state or RegionState()
        self._engine = engine or VectorizedMonteCarloEngine()
        self._config = config or SimulationConfig(n_iterations=20_000, seed=7)
        self._transition = transition or ClimateTransition()
        self._model_std = model_std
        self._rerun_threshold = rerun_threshold
        self._lock = threading.Lock()

        self._scenarios = scenarios or WildfireScenarioGenerator().generate(
            self._to_world_state()
        )
        # Baseline run populates the cached per-scenario risk + the initial picture.
        self._scenario_risk: dict[str, float] = {}
        self._computed_risk = self.predict_risk()

    # ── DigitalTwin interface ────────────────────────────────────────────────
    def get_current_state(self) -> RegionState:
        """A copy of the twin's physical state (callers can't mutate internals)."""
        return self._state.model_copy()

    @property
    def computed_risk_state(self) -> RiskState:
        """The twin's latest computed risk picture (no recomputation)."""
        return self._computed_risk

    @property
    def scenarios(self) -> ScenarioSet:
        """The twin's current (posterior) belief over scenarios."""
        return self._scenarios

    def predict_risk(self) -> RiskState:
        """Run Monte Carlo over the current state × beliefs → risk state."""
        run = self._engine.run(self._to_world_state(), self._scenarios, self._config)
        self._scenario_risk = self._scenario_means(run)
        self._computed_risk = self._build_risk_state(self._scenarios)
        return self._computed_risk

    def update_from_observation(self, observation: Observation) -> TwinUpdate:
        """Evolve the twin with one observation; recompute risk if it moved.

        Order matters: the **Bayesian belief update runs against the pre-transition
        state** (so the observation is compared to what each scenario predicted),
        *then* the deterministic transition evolves the present state, *then* Monte
        Carlo re-runs over the new state + posterior beliefs.
        """
        with self._lock:
            world_before = self._to_world_state()
            prior = self._scenarios
            posterior = GaussianBayesianUpdater(
                world_before, default_model_std=self._model_std
            ).update(prior, observation)
            shift = _total_variation(prior, posterior)
            self._scenarios = posterior

            state_changed = self._transition.apply(self._state, observation)
            recomputed = state_changed or shift >= self._rerun_threshold
            if recomputed:
                run = self._engine.run(self._to_world_state(), posterior, self._config)
                self._scenario_risk = self._scenario_means(run)
            self._computed_risk = self._build_risk_state(posterior)

            log.info(
                "twin.updated",
                twin_id=self.twin_id,
                variable=observation.variable,
                belief_shift=round(shift, 4),
                recomputed=recomputed,
                risk=round(self._computed_risk.risk, 1),
            )
            return TwinUpdate(
                twin_id=self.twin_id,
                risk_state=self._computed_risk,
                belief_shift=shift,
                recomputed=recomputed,
            )

    # ── internals: the engine boundary ───────────────────────────────────────
    def _to_world_state(self) -> WorldState:
        """Map the twin's current state onto the engine's ``WorldState`` (see
        :func:`region_to_world_state`)."""
        return region_to_world_state(self.twin_id, self._state)

    def _scenario_means(self, run: SimulationRun) -> dict[str, float]:
        return {o.scenario_id: o.risk.mean for o in run.outcomes}

    def _build_risk_state(self, scenarios: ScenarioSet) -> RiskState:
        risk = posterior_mixture_risk(scenarios, self._scenario_risk)
        return RiskState(
            region=self.twin_id,
            risk=risk,
            band=RiskBand.from_score(risk),
            confidence=scenario_confidence(scenarios),
            scenario_priors={s.id: s.prior for s in scenarios.scenarios},
        )
