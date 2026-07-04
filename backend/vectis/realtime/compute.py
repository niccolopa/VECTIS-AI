"""The shared compute pipeline — one tiered engine for every viewer (Session 38).

Before this module, T1/T2 compute for arbitrary global cells never ran in the API
server at all: the tile stream was screening-only, ``TierManager`` lived only in tests
and stress runs, and the single full pipeline (Session 25's ``LiveStreamBroadcaster``)
covered exactly one demo cell. This module is the missing piece — **one** loop that,
per tick:

    ingest (once) → screen (warming cadence) → TierManager (budgets, watchlist)
        → real per-cell Monte Carlo + Bayesian T1 → budgeted T2 board narration
        → results fanned out to every subscriber

No SSE connection ever runs simulation again: connections are bounded fan-out queues
(the ``LiveStreamBroadcaster`` pattern at global scope), so compute tracks **attention
plus real events** — never viewer count × grid size. This closes the Session-24
``ponytail`` note for good.

Honesty carried forward: every forecast here runs the same illustrative, uncalibrated
coefficients as everywhere else. Being watched, pinned, or promoted changes *when* a
cell is recomputed — never how accurate its number is.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from vectis.agents.board.schemas import BoardInput, ScenarioView
from vectis.agents.board.service import SimulationBoardService
from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.realtime.attention import AttentionRegistry, warming_partition
from vectis.realtime.events.base import CellId
from vectis.realtime.history import HistoryRecorder
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.pipeline import ForecastResult
from vectis.realtime.retention import RetentionPolicy
from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore
from vectis.realtime.tiering.manager import (
    PromotionDecision,
    TieringCycle,
    TierManager,
    headline_scores,
)
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.models.base import HazardModel
from vectis.simulation.models.cyclone import (
    CycloneScenarioGenerator,
    approaching_cyclone_state,
    default_cyclone_model,
)
from vectis.simulation.models.earthquake import (
    EarthquakeScenarioGenerator,
    aftershock_state,
    default_earthquake_model,
)
from vectis.simulation.models.flood import (
    FloodScenarioGenerator,
    default_flood_model,
    monsoon_flood_state,
)
from vectis.simulation.models.wildfire import default_wildfire_model
from vectis.simulation.probability.bayesian import GaussianBayesianUpdater, Observation
from vectis.simulation.probability.uncertainty import (
    confidence_from_entropy,
    posterior_mixture_risk,
)
from vectis.simulation.scenarios.base import ScenarioGenerator
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig, WorldState

logger = get_logger(__name__)

#: The screening/pipeline climatology baseline: absolute temperature → anomaly.
_CLIMATOLOGY_TEMP_C = 22.0


@dataclass(frozen=True)
class _HazardSeam:
    """Everything the T1 stage needs for one hazard — the Session-35 seams, bundled."""

    model_factory: Callable[[], HazardModel]
    generator: ScenarioGenerator
    twin_factory: Callable[[], WorldState]
    #: observed WorldCellState → {twin variable name: observed value} (only what's real)
    overlay: Callable[[WorldCellState], dict[str, float]]
    #: the hazard's primary driver as a Bayesian observation, or None if unobserved
    observation: Callable[[WorldCellState], Observation | None]


def _wildfire_overlay(state: WorldCellState) -> dict[str, float]:
    values: dict[str, float] = {}
    if state.temperature is not None:
        values["temp_anomaly_c"] = state.temperature - _CLIMATOLOGY_TEMP_C
    if (wind := state.extra.get("wind_speed_kmh")) is not None:
        values["wind_speed_kmh"] = wind
    return values


def _flood_overlay(state: WorldCellState) -> dict[str, float]:
    values: dict[str, float] = {}
    if state.precipitation_mm is not None:
        values["precipitation_mm"] = state.precipitation_mm
    if state.flood_alert_level is not None:
        values["flood_alert_level"] = state.flood_alert_level
    return values


def _days_since(state: WorldCellState) -> float:
    return max((datetime.now(UTC) - state.last_updated).total_seconds(), 0.0) / 86400.0


def _quake_overlay(state: WorldCellState) -> dict[str, float]:
    if state.earthquake_magnitude is None:
        return {}
    return {
        "mainshock_magnitude": state.earthquake_magnitude,
        "days_since_mainshock": _days_since(state),
    }


def _cyclone_overlay(state: WorldCellState) -> dict[str, float]:
    values: dict[str, float] = {}
    if state.cyclone_alert_level is not None:
        values["cyclone_alert_level"] = state.cyclone_alert_level
    if (wind := state.extra.get("wind_speed_kmh")) is not None:
        values["wind_speed_kmh"] = wind
    return values


def _obs(variable: str, value: float | None, std: float) -> Observation | None:
    return None if value is None else Observation(variable=variable, value=value, std=std)


#: hazard → its full T1 seam. Adding a hazard later = one entry, zero loop edits.
_SEAMS: dict[str, _HazardSeam] = {
    "wildfire": _HazardSeam(
        default_wildfire_model, WildfireScenarioGenerator(), california_wildfire_state,
        _wildfire_overlay,
        lambda s: _obs(
            "temp_anomaly_c",
            None if s.temperature is None else s.temperature - _CLIMATOLOGY_TEMP_C,
            0.5,
        ),
    ),
    "flood": _HazardSeam(
        default_flood_model, FloodScenarioGenerator(), monsoon_flood_state,
        _flood_overlay,
        lambda s: _obs("precipitation_mm", s.precipitation_mm, 5.0),
    ),
    "quake": _HazardSeam(
        default_earthquake_model, EarthquakeScenarioGenerator(), aftershock_state,
        _quake_overlay,
        lambda s: _obs("mainshock_magnitude", s.earthquake_magnitude, 0.15),
    ),
    "cyclone": _HazardSeam(
        default_cyclone_model, CycloneScenarioGenerator(), approaching_cyclone_state,
        _cyclone_overlay,
        lambda s: _obs("cyclone_alert_level", s.cyclone_alert_level, 0.15),
    ),
}


class CellForecastRunner:
    """The real T1 stage for one arbitrary global cell — Monte Carlo + Bayesian.

    Exactly the machinery the Session-35 multi-hazard proof drives, productionized:
    the hazard's digital-twin baseline with the cell's **observed** drivers projected
    over it, the hazard's scenario branches re-weighted by a Gaussian Bayesian update
    on the primary driver, one vectorized Monte Carlo run, and the posterior-mixture
    headline risk. No per-hazard code in the loop — the seams carry it all.
    """

    def __init__(self, *, config: SimulationConfig | None = None) -> None:
        # ponytail: 2k draws per live T1 (vs 8k in the demo pipeline) keeps a full
        # 64-cell budget cycle in the hundreds of ms; raise via VECTIS_T1_ITERATIONS.
        self._config = config or SimulationConfig(
            n_iterations=int(os.getenv("VECTIS_T1_ITERATIONS", "2000")),
            seed=38, parallel=False, n_workers=1,
        )
        self._engines: dict[str, VectorizedMonteCarloEngine] = {}

    def forecast(
        self, state: WorldCellState, hazard: str
    ) -> tuple[ForecastResult, BoardInput]:
        """One full T1 forecast of ``state`` for ``hazard`` (must be a seamed hazard)."""
        seam = _SEAMS[hazard]
        base = seam.twin_factory()
        observed = seam.overlay(state)
        if observed:  # project real cell state over the illustrative twin baseline
            base = base.model_copy(
                update={
                    "variables": [
                        v.model_copy(update={"value": observed[v.name]})
                        if v.name in observed else v
                        for v in base.variables
                    ]
                }
            )
        scenarios = seam.generator.generate(base)
        observation = seam.observation(state)
        if observation is not None:
            scenarios = GaussianBayesianUpdater(base).update(scenarios, observation)

        engine = self._engines.get(hazard)
        if engine is None:
            engine = self._engines[hazard] = VectorizedMonteCarloEngine(
                hazard=seam.model_factory()
            )
        run = engine.run(base, scenarios, self._config)

        scenario_risk = {o.scenario_id: o.risk.mean for o in run.outcomes}
        risk = posterior_mixture_risk(scenarios, scenario_risk)
        posterior = {s.id: s.prior for s in scenarios.scenarios}
        result = ForecastResult(
            cell_id=state.cell_id,
            risk_score=risk,
            confidence=confidence_from_entropy(list(posterior.values())),
            risk_band=RiskBand.from_score(risk),
            posterior=posterior,
            run=run,
        )
        dominant = max(scenarios.scenarios, key=lambda s: s.prior)
        board_input = BoardInput(
            region=f"{hazard} cell {state.cell_id}",
            risk_score=result.risk_score,
            confidence=result.confidence,
            risk_band=result.risk_band,
            primary_driver=dominant.name,
            scenarios=[
                ScenarioView(
                    id=s.id, name=s.name, description=s.description, probability=s.prior
                )
                for s in scenarios.scenarios
            ],
        )
        return result, board_input


class SharedComputeLoop:
    """One global tick: ingest once, screen on the warming cadence, tier, forecast, narrate.

    The single owner of expensive compute. Terminal SSE connections subscribe to its
    output (or, transitionally, to the ingestion broadcaster it feeds) — they never
    trigger simulation. ``run_cycle`` is synchronous and deterministic so tests and
    load proofs drive ticks directly, exactly like ``GlobalIngestionBroadcaster.poll_once``.
    """

    def __init__(
        self,
        *,
        store: StateStore[WorldCellState],
        attention: AttentionRegistry,
        ingestion: GlobalIngestionBroadcaster,
        tier: TierManager | None = None,
        runner: CellForecastRunner | None = None,
        board: SimulationBoardService | None = None,
        history: HistoryRecorder | None = None,
        retention: RetentionPolicy | None = None,
        retention_every: int = 240,
        tick_seconds: float = 30.0,
    ) -> None:
        self._store = store
        self._attention = attention
        self._ingestion = ingestion
        self._tier = tier or TierManager()
        self._runner = runner or CellForecastRunner()
        self._board = board
        #: Session 39: every T1 forecast / T2 report is snapshotted durably (None = off).
        self._history = history
        #: Session 39: bound the durable history in time. Enforced every
        #: ``retention_every`` ticks (≈2h at 30s ticks) — a real cadence, not just docs.
        self._retention = retention if retention is not None else (
            RetentionPolicy() if history is not None else None
        )
        self._retention_every = retention_every
        self._tick_seconds = tick_seconds
        self._sweeper = GlobalScreeningSweep()
        self._task: asyncio.Task[None] | None = None

        #: latest T1/T2 forecast per cell — what the cell-brief endpoint serves.
        self.results: dict[CellId, ForecastResult] = {}
        #: last known screening scores per cell (plain floats) — the fan-out layer's
        #: shared source; merged across warm ticks so partial sweeps never blank cells.
        self.latest_scores: dict[CellId, dict[str, float]] = {}
        self.last_cycle: TieringCycle | None = None
        self.tick = 0
        self.forecasts_run = 0
        self.reports_generated = 0
        #: honest load accounting: cells screened this tick / in total — what the
        #: attention-bounded load proof compares against viewer count × grid size.
        self.cells_screened_last = 0
        self.cells_screened_total = 0
        self._board_inputs: dict[CellId, BoardInput] = {}

    # ── one deterministic tick ────────────────────────────────────────────────────
    def run_cycle(self) -> list[dict[str, Any]]:
        """Ingest → screen (warming cadence) → tier → T1 → T2. Returns the event views."""
        views = self._ingestion.poll_once()

        states = self._store.active_states()
        to_screen = warming_partition(self.tick, states, self._attention)
        self.cells_screened_last = len(to_screen)
        self.cells_screened_total += len(to_screen)
        sweep = self._sweeper.sweep(to_screen)

        # Merge fresh scores over the last known ones; forget evicted cells.
        active = {s.cell_id for s in states}
        for cell_id, hazards in sweep.items():
            self.latest_scores[cell_id] = {h: s.value for h, s in hazards.items()}
        for cell_id in [c for c in self.latest_scores if c not in active]:
            del self.latest_scores[cell_id]
            self.results.pop(cell_id, None)  # an evicted cell's forecast is stale too

        self._tier.set_watchlist(self._attention.watchlisted())
        cycle = self._tier.run_cycle(headline_scores(sweep), t1_runner=self._run_t1)

        for slot in cycle.board_slots:  # T2 — hard-budgeted by the manager (≤ max_t2)
            result = self.results.get(slot.cell_id)
            board_input = self._board_inputs.pop(slot.cell_id, None)
            if self._board is None or result is None or board_input is None:
                continue
            result.report = self._board.analyze(board_input)
            self.reports_generated += 1
            logger.info(
                "[INFO] T2 board report for cell %s (risk %.1f, watchlisted=%s)",
                slot.cell_id, slot.risk, slot.watchlisted,
            )
            if self._history is not None:
                state = self._store.get_state(slot.cell_id)
                if state is not None:
                    scores = self.latest_scores.get(slot.cell_id, {})
                    self._history.record_forecast(
                        state, result,
                        hazard=max(scores, key=lambda h: scores[h]) if scores else "",
                        screening=scores, trigger="board_report",
                    )

        # Bound the durable history in time on a cadence (best-effort inside the policy).
        if (
            self._retention is not None
            and self._retention_every > 0
            and self.tick % self._retention_every == 0
        ):
            self._retention.enforce()

        self.last_cycle = cycle
        self.tick += 1
        return views

    def _run_t1(self, batch: Sequence[PromotionDecision]) -> dict[CellId, float]:
        """The tiering engine's T1 runner: a real forecast per granted slot."""
        risks: dict[CellId, float] = {}
        for decision in batch:
            state = self._store.get_state(decision.cell_id)
            hazards = self.latest_scores.get(decision.cell_id)
            if state is None or not hazards:
                continue  # evicted or unscreenable since promotion — nothing to forecast
            worst = max(hazards, key=lambda h: hazards[h])
            if worst not in _SEAMS:
                continue
            try:
                result, board_input = self._runner.forecast(state, worst)
            except Exception:
                logger.exception("[ERROR] T1 forecast failed for cell %s", decision.cell_id)
                continue
            self.results[decision.cell_id] = result
            self._board_inputs[decision.cell_id] = board_input
            self.forecasts_run += 1
            risks[decision.cell_id] = result.risk_score
            if self._history is not None:
                self._history.record_forecast(
                    state, result, hazard=worst, screening=hazards, trigger="t1_forecast"
                )
        return risks

    # ── lifecycle: the background task the app runs ───────────────────────────────
    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                views = await asyncio.to_thread(self.run_cycle)
            except Exception:
                logger.exception("[ERROR] shared compute cycle failed; retrying next tick")
                views = []
            # Feed the ingestion broadcaster's subscribers (the terminal tape) so one
            # loop drives both — the broadcaster's own task stays parked.
            self._ingestion.publish(views)
            await asyncio.sleep(self._tick_seconds)

    async def subscribe(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Event batches, via the ingestion broadcaster this loop feeds."""
        async for batch in self._ingestion.subscribe():
            yield batch
