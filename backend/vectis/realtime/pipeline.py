"""ContinuousPipeline — the single living flow that unites every V3 layer.

Sessions 16–21 each built one isolated organ. This module is the nervous system that
wires them into one continuous loop::

    Live Data → Events → Kalman State → Bayesian Update → Monte Carlo → Decision Report
     (broker)  (consumer)  (Session 20)   (Session 21)    (V2 engine)   (V2 board)

The flow splits into a **fast path** and a **slow path** — the key to keeping it
responsive under load:

- **Fast path** (``process_event``, the consumer callback — sub-millisecond, synchronous):
  fold the observation into the cell's Kalman belief, then run the continuous Bayesian
  update to get the new posterior over scenarios. Pure ``math``/arithmetic, so it keeps up
  with a high event rate and the consumer acks immediately.
- **Slow path** (``_forecast_loop`` — a background worker): the compute-heavy Monte Carlo
  cycle (numpy, can be 100s of ms) and, only when the risk moves materially, the LangGraph
  decision board. It runs **off the event loop** via :func:`asyncio.to_thread`, and a burst
  of events for one cell **coalesces** to a single forecast of the latest state — so the
  expensive stage can never become a per-event bottleneck or block ingestion.

The Math Firewall holds end to end: every number is produced by the deterministic engines;
the LLM board only narrates the figures it is handed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass

from vectis.agents.board.schemas import BoardInput, DecisionIntelligenceReport, ScenarioView
from vectis.agents.board.service import SimulationBoardService
from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.realtime.events.base import CellId, GlobalEvent
from vectis.realtime.forecasting.bayesian.likelihood import ScenarioProfile
from vectis.realtime.forecasting.bayesian.priors import ScenarioPriors
from vectis.realtime.forecasting.bayesian.updater import ContinuousBayesianUpdater
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState
from vectis.realtime.forecasting.kalman.updater import KalmanStateUpdater
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MemoryBroker, MessageBroker
from vectis.realtime.streams.consumer import EventConsumer
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.probability.uncertainty import (
    confidence_from_entropy,
    posterior_mixture_risk,
)
from vectis.simulation.scenarios.generator import WildfireScenarioGenerator, liguria_wildfire_state
from vectis.simulation.schemas import (
    Scenario,
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    WorldState,
)

logger = get_logger(__name__)

# Human label per dominant scenario, for the report's primary driver (firewall-safe text).
_DRIVER_LABELS: dict[str, str] = {
    "baseline": "Prevailing seasonal conditions",
    "hotter_drier": "Temperature & rainfall anomaly",
    "extreme_wind": "Wind-driven ignition spread",
}

# Bridge between the two vocabularies that meet at the Kalman→Monte-Carlo boundary:
#   Kalman/Bayesian key (what KalmanStateUpdater stores) → (WorldState variable it drives,
#   additive offset applied to the mean).
# The offset converts an absolute reading to the anomaly the hazard model expects — the
# weather feed reports absolute °C, but the model's ``temp_anomaly_c`` is an anomaly versus a
# ~22 °C seasonal climatology (so a 24 °C reading lands as the +2 °C twin baseline).
# Without this map the temperature estimate — the model's strongest driver — matched no
# WorldState variable and was silently dropped, leaving risk to move only via Bayesian
# reweighting (the external audit's finding).
# ponytail: hand-set climatology baseline; wire to per-cell climatology in calibration (S26).
KALMAN_TO_WORLD: dict[str, tuple[str, float]] = {
    "temperature": ("temp_anomaly_c", -22.0),
    "wind_speed_kmh": ("wind_speed_kmh", 0.0),
}


@dataclass(slots=True)
class ForecastResult:
    """The slow path's output for one cell — the continuously-updated forecast."""

    cell_id: CellId
    risk_score: float
    confidence: float
    risk_band: RiskBand
    posterior: dict[str, float]
    run: SimulationRun
    report: DecisionIntelligenceReport | None = None


@dataclass(slots=True)
class _ForecastJob:
    """A pending slow-path request: run the heavy forecast for this cell's latest state."""

    cell_id: CellId
    state: KalmanCellState
    posterior: dict[str, float]


def default_scenario_profiles() -> dict[str, ScenarioProfile]:
    """Bayesian archetypes for the three wildfire branches, keyed on Kalman variables.

    Variable names are the canonical keys the :class:`KalmanStateUpdater` stores
    (``temperature`` etc. — see ``state.updater.VARIABLE_FIELDS``); a feed emitting
    ``temp_anomaly_c`` lands here as ``temperature``.
    """
    return {
        "baseline": ScenarioProfile(
            scenario_id="baseline",
            expected={"temperature": 24.0, "drought_index": 0.30, "wind_speed_kmh": 15.0},
            spread={"temperature": 6.0, "drought_index": 0.25, "wind_speed_kmh": 12.0},
        ),
        "hotter_drier": ScenarioProfile(
            scenario_id="hotter_drier",
            expected={"temperature": 38.0, "drought_index": 0.75, "wind_speed_kmh": 20.0},
            spread={"temperature": 6.0, "drought_index": 0.25, "wind_speed_kmh": 12.0},
        ),
        "extreme_wind": ScenarioProfile(
            scenario_id="extreme_wind",
            expected={"temperature": 30.0, "drought_index": 0.50, "wind_speed_kmh": 55.0},
            spread={"temperature": 6.0, "drought_index": 0.25, "wind_speed_kmh": 14.0},
        ),
    }


class ContinuousPipeline:
    """Orchestrate the continuous Live-Data → Decision-Report flow over a broker stream.

    All collaborators are injected so the pipeline is testable and the transport is
    swappable; :func:`build_default_pipeline` wires the offline Liguria-wildfire defaults.

    :param risk_change_threshold: minimum absolute move in headline risk (0–100) since the
        last report for a cell before the (expensive) decision board is re-run. Damps churn
        so the LLM board only fires on a material change.

    ponytail: one Bayesian belief + one base ``WorldState`` — correct for the single-region
    (Liguria) demo. Per-cell beliefs become a ``dict[CellId, ...]`` when multi-region lands;
    the rest of the flow is already keyed by ``cell_id``.
    """

    def __init__(
        self,
        *,
        broker: MessageBroker,
        kalman: KalmanStateUpdater,
        bayesian: ContinuousBayesianUpdater,
        engine: VectorizedMonteCarloEngine,
        board: SimulationBoardService,
        base_state: WorldState,
        scenarios: ScenarioSet,
        config: SimulationConfig,
        topic: str = DEFAULT_TOPIC,
        risk_change_threshold: float = 5.0,
    ) -> None:
        self._broker = broker
        self._kalman = kalman
        self._bayesian = bayesian
        self._engine = engine
        self._board = board
        self._base_state = base_state
        self._scenarios = scenarios
        self._config = config
        self._risk_change_threshold = risk_change_threshold

        self._consumer = EventConsumer(broker, self.process_event, topic=topic)
        # Slow-path queue with per-cell coalescing: only the latest job per cell is kept,
        # so a burst of events collapses to one forecast of the freshest state.
        self._forecast_queue: asyncio.Queue[CellId] = asyncio.Queue()
        self._jobs: dict[CellId, _ForecastJob] = {}
        self._pending: set[CellId] = set()

        self._last_risk: dict[CellId, float] = {}
        #: Latest forecast per cell — the pipeline's continuously-updated output.
        self.results: dict[CellId, ForecastResult] = {}
        self.forecasts_run = 0
        self.reports_generated = 0

    # ── fast path: runs inside the consumer, must stay cheap ─────────────────────
    def process_event(self, event: GlobalEvent) -> None:
        """Kalman + Bayesian update for one event, then enqueue the heavy forecast.

        Synchronous and sub-millisecond: the consumer acks as soon as this returns, so
        ingestion throughput is bounded by the cheap math, never by Monte Carlo.
        """
        observation = event.to_observation()
        state = self._kalman.apply_observation(observation)
        posterior = self._bayesian.update_probabilities(state)
        self._enqueue_forecast(_ForecastJob(state.cell_id, state, dict(posterior)))

    def _enqueue_forecast(self, job: _ForecastJob) -> None:
        """Register the latest job for a cell; queue the cell once while one is pending."""
        self._jobs[job.cell_id] = job  # always keep the freshest state
        if job.cell_id not in self._pending:
            self._pending.add(job.cell_id)
            self._forecast_queue.put_nowait(job.cell_id)

    # ── slow path: heavy compute off the event loop ──────────────────────────────
    async def _forecast_loop(self) -> None:
        """Drain forecast jobs forever, running the compute-heavy stages off the loop."""
        while True:
            cell_id = await self._forecast_queue.get()
            try:
                job = self._jobs.pop(cell_id, None)
                self._pending.discard(cell_id)
                if job is not None:
                    await self._run_forecast(job)
            except Exception:  # a bad forecast must not kill the worker
                logger.exception("[ERROR] forecast failed for cell %s", cell_id)
            finally:
                self._forecast_queue.task_done()

    async def _run_forecast(self, job: _ForecastJob) -> None:
        """Monte Carlo + (conditionally) the decision board, all off the event loop."""
        # Monte Carlo is CPU-bound numpy — run it in a thread so the loop stays free.
        result = await asyncio.to_thread(self._compute_forecast, job)

        prior_risk = self._last_risk.get(job.cell_id)
        moved = prior_risk is None or abs(result.risk_score - prior_risk) >= self._risk_change_threshold
        if moved:
            # The board is LLM-bound (network/CPU) — also keep it off the loop.
            result.report = await asyncio.to_thread(self._board.analyze, self._board_input(result))
            self.reports_generated += 1
            logger.info(
                "[INFO] cell %s risk %.1f (%s) — new decision report %s",
                job.cell_id, result.risk_score, result.risk_band.value, result.report.report_id,
            )

        self._last_risk[job.cell_id] = result.risk_score
        self.results[job.cell_id] = result

    def _compute_forecast(self, job: _ForecastJob) -> ForecastResult:
        """Pure, blocking forecast math — safe to run in a worker thread."""
        self.forecasts_run += 1
        state = self._overlay_state(job.state)
        scenarios = self._reweighted_scenarios(job.posterior)
        run = self._engine.run(state, scenarios, self._config)

        scenario_risk = {o.scenario_id: o.risk.mean for o in run.outcomes}
        risk_score = posterior_mixture_risk(scenarios, scenario_risk)
        confidence = confidence_from_entropy(list(job.posterior.values()))
        return ForecastResult(
            cell_id=job.cell_id,
            risk_score=risk_score,
            confidence=confidence,
            risk_band=RiskBand.from_score(risk_score),
            posterior=job.posterior,
            run=run,
        )

    def _overlay_state(self, kalman_state: KalmanCellState) -> WorldState:
        """Project the live Kalman means onto the base WorldState via :data:`KALMAN_TO_WORLD`.

        Translates each Kalman/Bayesian variable to the WorldState variable it drives,
        applying the offset that bridges absolute readings to model anomalies, so the
        Kalman estimate (not just the Bayesian reweighting) actually moves the Monte Carlo.
        """
        state = self._base_state.model_copy(deep=True)
        by_name = {var.name: var for var in state.variables}
        for kalman_var, (world_var, offset) in KALMAN_TO_WORLD.items():
            estimate = kalman_state.estimates.get(kalman_var)
            target = by_name.get(world_var)
            if estimate is not None and target is not None:
                target.value = estimate.mean + offset
        return state

    def _reweighted_scenarios(self, posterior: Mapping[str, float]) -> ScenarioSet:
        """Replace the base scenarios' priors with the Bayesian posterior weights."""
        return ScenarioSet(
            scenarios=[
                Scenario(
                    id=s.id, name=s.name, description=s.description,
                    perturbations=s.perturbations, prior=posterior.get(s.id, s.prior),
                )
                for s in self._scenarios.scenarios
            ]
        )

    def _board_input(self, result: ForecastResult) -> BoardInput:
        """Assemble the board's source-of-truth numbers from a forecast (firewall-safe)."""
        views = [
            ScenarioView(
                id=s.id, name=s.name, description=s.description,
                probability=result.posterior.get(s.id, s.prior),
            )
            for s in self._scenarios.scenarios
        ]
        dominant = max(views, key=lambda v: v.probability, default=None)
        driver = _DRIVER_LABELS.get(dominant.id, dominant.name) if dominant else "Undetermined"
        return BoardInput(
            region=self._base_state.region,
            risk_score=result.risk_score,
            confidence=result.confidence,
            risk_band=result.risk_band,
            primary_driver=driver,
            scenarios=views,
        )

    # ── lifecycle ────────────────────────────────────────────────────────────────
    async def start(self, *, max_events: int | None = None) -> int:
        """Run the pipeline: a forecast worker plus the broker consumer.

        Without ``max_events`` this runs forever. ``max_events`` bounds the consumer for
        tests/batch drains; on return, all enqueued forecasts are drained before the worker
        stops, so the full Kalman→Bayesian→MC→Report flow has completed for every event.
        Returns the number of events successfully processed.
        """
        worker = asyncio.create_task(self._forecast_loop())
        try:
            processed = await self._consumer.run(max_events=max_events)
            await self._forecast_queue.join()  # let the slow path catch up before stopping
            return processed
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


def build_default_pipeline(
    *,
    broker: MessageBroker | None = None,
    board: SimulationBoardService | None = None,
    n_iterations: int = 20_000,
    seed: int = 7,
    region: str = "liguria",
) -> ContinuousPipeline:
    """Wire the offline Liguria-wildfire pipeline with sensible defaults.

    Memory broker, a fresh Kalman store, the three-branch wildfire scenarios, and the
    V2 Monte Carlo engine + decision board (mock LLM by default → runs offline, no key).
    """
    store: MemoryStateStore[KalmanCellState] = MemoryStateStore()
    kalman = KalmanStateUpdater(store)

    profiles = default_scenario_profiles()
    priors = ScenarioPriors(
        {"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
        baseline={"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
        relax_rate=0.0,
    )
    bayesian = ContinuousBayesianUpdater(profiles, priors)

    base_state = liguria_wildfire_state(region)
    scenarios = WildfireScenarioGenerator().generate(base_state)
    config = SimulationConfig(n_iterations=n_iterations, seed=seed)

    return ContinuousPipeline(
        broker=broker or MemoryBroker(),
        kalman=kalman,
        bayesian=bayesian,
        engine=VectorizedMonteCarloEngine(),
        board=board or SimulationBoardService(),
        base_state=base_state,
        scenarios=scenarios,
        config=config,
    )
