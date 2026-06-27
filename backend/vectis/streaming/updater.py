"""Real-time orchestrator — the seam between live data and the math engines.

:class:`RealTimeUpdater` owns the current belief state for a region and turns a
single incoming event into a decision:

1. **Register** the event → an :class:`Observation`.
2. **Debounce**: drop content-duplicates seen inside a short window (so 100
   identical readings/sec don't become 100 Bayesian updates — which would also be
   *mathematically* wrong, double-counting one measurement).
3. **Bayesian update**: revise the scenario beliefs (Session 8).
4. **Decide**: if the belief shift (total-variation distance) is significant,
   **re-run Monte Carlo** (Session 7) to refresh the risk distribution; otherwise
   reuse the per-scenario risk from the last full run (cheap re-weighting).
5. **Emit** a :class:`StateChange` describing the new picture.

`process` is **pure, synchronous, and transport-agnostic** — it neither awaits nor
knows about WebSockets, threads, or HTTP. That is the swappable seam: FastAPI
BackgroundTasks call it today; a Celery worker or Kafka consumer could call the
exact same method tomorrow with zero change to the math.

A single in-process lock guards the shared belief state. ponytail: global lock —
fine for one region in one process; shard to per-region locks (or a Redis lock)
when this serves many regions or scales out.
"""

from __future__ import annotations

import threading
import time

from vectis.core.logging import get_logger
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.probability.bayesian import GaussianBayesianUpdater
from vectis.simulation.probability.uncertainty import (
    posterior_mixture_risk,
    scenario_confidence,
)
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    liguria_wildfire_state,
)
from vectis.simulation.schemas import (
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    WorldState,
)
from vectis.streaming.events import RiskState, StateChange, StreamEvent

log = get_logger(__name__)


def _total_variation(prior: ScenarioSet, posterior: ScenarioSet) -> float:
    """TV distance between two beliefs over the same scenarios: ½·Σ|Δprior|."""
    post = {s.id: s.prior for s in posterior.scenarios}
    return 0.5 * sum(abs(s.prior - post.get(s.id, 0.0)) for s in prior.scenarios)


class RealTimeUpdater:
    """Stateful orchestrator: event in → (Bayesian update, maybe MC) → StateChange."""

    def __init__(
        self,
        *,
        state: WorldState,
        scenarios: ScenarioSet,
        engine: VectorizedMonteCarloEngine | None = None,
        config: SimulationConfig | None = None,
        rerun_threshold: float = 0.02,
        debounce_seconds: float = 1.0,
    ) -> None:
        self._state = state
        self._scenarios = scenarios  # current belief (prior → posterior over time)
        self._engine = engine or VectorizedMonteCarloEngine()
        self._updater = GaussianBayesianUpdater(state)
        self._config = config or SimulationConfig(n_iterations=20_000, seed=7)
        self._rerun_threshold = rerun_threshold
        self._debounce_seconds = debounce_seconds

        self._lock = threading.Lock()
        self._recent: dict[str, float] = {}  # dedupe_key → monotonic time last seen
        self._scenario_risk: dict[str, float] = {}  # scenario_id → mean risk (last MC run)
        self._risk = self._reduce_run(self._engine.run(state, scenarios, self._config))

    # ── read-only views ──────────────────────────────────────────────────────
    @property
    def risk_state(self) -> RiskState:
        """The current real-time risk picture."""
        with self._lock:
            return self._risk

    @property
    def scenarios(self) -> ScenarioSet:
        """The current (posterior) belief over scenarios."""
        with self._lock:
            return self._scenarios

    # ── the swappable seam ───────────────────────────────────────────────────
    def process(self, event: StreamEvent) -> StateChange | None:
        """Apply one event. Returns a :class:`StateChange`, or ``None`` if debounced.

        Synchronous and self-contained: safe to call from a thread, a background
        task, or a future Celery/Kafka worker. Thread-safe via an internal lock.
        """
        with self._lock:
            if self._is_duplicate(event):
                log.info("stream.debounced", event_id=event.event_id, source=event.source)
                return None

            prior = self._scenarios
            posterior = self._updater.update(prior, event.to_observation())
            shift = _total_variation(prior, posterior)
            self._scenarios = posterior

            triggered = shift >= self._rerun_threshold
            if triggered:
                self._scenario_risk = self._scenario_means(
                    self._engine.run(self._state, posterior, self._config)
                )
            self._risk = self._build_risk_state(posterior)

            log.info(
                "stream.processed",
                event_id=event.event_id,
                belief_shift=round(shift, 4),
                triggered_rerun=triggered,
                risk=round(self._risk.risk, 1),
                confidence=round(self._risk.confidence, 3),
            )
            return StateChange(
                event_id=event.event_id,
                triggered_rerun=triggered,
                belief_shift=shift,
                risk=self._risk,
            )

    # ── internals ────────────────────────────────────────────────────────────
    def _is_duplicate(self, event: StreamEvent) -> bool:
        """Content-debounce: True if this measurement was seen within the window.

        ponytail: in-memory dict + monotonic clock — the blueprint. Swap for a
        Redis key with TTL when ingestion is multi-process.
        """
        if self._debounce_seconds <= 0.0:
            return False
        now = time.monotonic()
        key = event.dedupe_key()
        last = self._recent.get(key)
        # Opportunistically evict stale keys so the map can't grow unbounded.
        self._recent = {
            k: t for k, t in self._recent.items() if now - t < self._debounce_seconds
        }
        self._recent[key] = now
        return last is not None and (now - last) < self._debounce_seconds

    def _scenario_means(self, run: SimulationRun) -> dict[str, float]:
        return {o.scenario_id: o.risk.mean for o in run.outcomes}

    def _reduce_run(self, run: SimulationRun) -> RiskState:
        """Seed initial risk state from the baseline run (also caches per-scenario risk)."""
        self._scenario_risk = self._scenario_means(run)
        return self._build_risk_state(self._scenarios)

    def _build_risk_state(self, scenarios: ScenarioSet) -> RiskState:
        from vectis.core.schemas import RiskBand

        risk = posterior_mixture_risk(scenarios, self._scenario_risk)
        return RiskState(
            region=self._state.region,
            risk=risk,
            band=RiskBand.from_score(risk),
            confidence=scenario_confidence(scenarios),
            scenario_priors={s.id: s.prior for s in scenarios.scenarios},
        )


def build_default_updater() -> RealTimeUpdater:
    """Construct the Liguria wildfire real-time updater used by the API.

    ponytail: hard-wired to the Liguria digital twin (the only live vertical).
    Generalize to a per-region registry when a second region lands.
    """
    state = liguria_wildfire_state()
    scenarios = WildfireScenarioGenerator().generate(state)
    return RealTimeUpdater(state=state, scenarios=scenarios)
