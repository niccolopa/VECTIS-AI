"""Live V3 climate-risk stream — a continuously-updating frame source for the API/UI.

The terminal demo (`scripts/demo_v3_live`) renders the V3 ``ContinuousPipeline`` to
stdout. This module exposes the *same* living pipeline as a stream of JSON-serializable
**frames** so the React console can subscribe over Server-Sent Events and animate the
risk shifting in real time.

    IngestionManager(ramping feeds) → EventProducer → broker
        → ContinuousPipeline (Kalman → Bayesian → Monte Carlo → Decision Report)
        → frame dict  (risk · Kalman state · posterior · raw events · report id)

Each connection wires its own pipeline, so every viewer watches the escalation from a
calm baseline. Offline and deterministic: no API key, no network — the ramping feeds
synthesize an escalating fire day, the deterministic engines produce every number.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider
from vectis.core.logging import get_logger
from vectis.realtime.connectors.satellite import SatelliteAPIConnector
from vectis.realtime.connectors.weather import WeatherAPIConnector, WeatherEvent
from vectis.realtime.events.base import GlobalEvent, naive_cell_id
from vectis.realtime.forecasting.bayesian.priors import ScenarioPriors
from vectis.realtime.forecasting.bayesian.updater import ContinuousBayesianUpdater
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState
from vectis.realtime.forecasting.kalman.updater import KalmanStateUpdater
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.pipeline import (
    _DRIVER_LABELS,
    ContinuousPipeline,
    ForecastResult,
    default_scenario_profiles,
)
from vectis.realtime.state.store import MemoryStateStore
from vectis.realtime.streams.broker import DEFAULT_TOPIC, MemoryBroker
from vectis.realtime.streams.producer import EventProducer
from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
from vectis.simulation.scenarios.generator import WildfireScenarioGenerator, liguria_wildfire_state
from vectis.simulation.schemas import SimulationConfig

logger = get_logger(__name__)

CELL_LABEL = "Liguria_01"  # friendly name for the grid cell the Liguria feeds map to


# ── ramping mock feeds — the engine of the "live" feeling ─────────────────────
class RampingWeatherConnector(WeatherAPIConnector):
    """Offline weather feed whose readings drift hotter & drier on every poll.

    Each ``fetch`` advances a tick: temperature climbs, humidity falls, wind rises,
    and a drought index deepens — a plausible escalating fire day. Drought has no
    slot in the base weather payload, so we emit it as an extra normalized event.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0

    def fetch(self) -> dict[str, Any]:
        t = self._tick
        self._tick += 1
        return {
            "temperature": 24.0 + 2.1 * t,            # heat anomaly building
            "humidity": max(8.0, 55.0 - 4.5 * t),     # air drying out
            "wind": 12.0 + 2.5 * t,                   # wind freshening
            "drought": min(0.95, 0.30 + 0.05 * t),    # drought index rising
        }

    def normalize(self, raw: dict[str, Any]) -> list[GlobalEvent]:
        events = super().normalize(raw)  # temp_anomaly_c / humidity_pct / wind_speed_kmh
        if raw.get("drought") is not None:
            events.append(
                WeatherEvent(
                    source=self.source,
                    location=self.location,
                    payload={"variable": "drought_index", "value": float(raw["drought"])},
                )
            )
        return events


class EscalatingSatelliteConnector(SatelliteAPIConnector):
    """Offline FIRMS-style feed whose fire-radiative-power grows each poll."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0

    def fetch(self) -> dict[str, Any]:
        t = self._tick
        self._tick += 1
        return {
            "detections": [
                {
                    "latitude": 44.41,
                    "longitude": 8.93,
                    "frp": 5.0 + 7.0 * t,
                    "confidence": min(95, 60 + 5 * t),
                }
            ]
        }


class LiveClimateStream:
    """Wire the live Liguria pipeline and emit one renderable frame per tick.

    Mirrors ``build_default_pipeline`` but keeps the Kalman store + ingestion manager
    references the frame builder needs (variance, raw events). The pipeline's bootstrap
    *is* the wiring — kept here, not in a script, so the API can reuse it cleanly.
    """

    def __init__(
        self,
        *,
        n_iterations: int = 8_000,
        seed: int = 7,
        region: str = "liguria",
        llm: LLMProvider | None = None,
    ) -> None:
        self._store: MemoryStateStore[KalmanCellState] = MemoryStateStore()
        kalman = KalmanStateUpdater(self._store)
        bayesian = ContinuousBayesianUpdater(
            default_scenario_profiles(),
            ScenarioPriors(
                {"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
                baseline={"baseline": 0.5, "hotter_drier": 0.3, "extreme_wind": 0.2},
                # >0 so the belief is never pinned at 0/100 — it can swing toward
                # hotter_drier as the evidence mounts, then settle.
                relax_rate=0.4,
            ),
        )
        base_state = liguria_wildfire_state(region)
        scenarios = WildfireScenarioGenerator().generate(base_state)
        broker = MemoryBroker()
        self._pipeline = ContinuousPipeline(
            broker=broker,
            kalman=kalman,
            bayesian=bayesian,
            engine=VectorizedMonteCarloEngine(),
            board=SimulationBoardService(llm=llm),
            base_state=base_state,
            scenarios=scenarios,
            config=SimulationConfig(n_iterations=n_iterations, seed=seed),
            risk_change_threshold=2.0,
        )

        weather = RampingWeatherConnector()
        satellite = EscalatingSatelliteConnector()
        self._manager = IngestionManager([weather, satellite])
        self._producer = EventProducer(self._manager, broker, topic=DEFAULT_TOPIC)
        # Both feeds report at Liguria's centroid → the same grid cell.
        self._cell_id = naive_cell_id(weather.location)
        self._last_report_id: str | None = None

    @property
    def pipeline(self) -> ContinuousPipeline:
        return self._pipeline

    async def frames(
        self, *, ticks: int | None = None, tick_seconds: float = 1.5
    ) -> AsyncIterator[dict[str, Any]]:
        """Drive the pipeline and yield one JSON-serializable frame per tick.

        ``ticks=None`` runs until the consumer stops iterating (client disconnect).
        Each tick: poll the ramping feeds → publish → drain the pipeline (Kalman →
        Bayesian → Monte Carlo → report) → emit the new state.
        """
        prev: dict[str, Any] | None = None
        tick = 0
        while ticks is None or tick < ticks:
            events = await asyncio.to_thread(self._manager.poll_once)
            published = await self._producer.publish(events)
            await self._pipeline.start(max_events=published)
            frame = self._frame(tick, events, prev)
            if frame is not None:
                yield frame
                prev = frame
            tick += 1
            if (ticks is None or tick < ticks) and tick_seconds:
                await asyncio.sleep(tick_seconds)

    def _frame(
        self, tick: int, events: list[GlobalEvent], prev: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Read the pipeline's latest output for the cell into a JSON frame."""
        result: ForecastResult | None = self._pipeline.results.get(self._cell_id)
        state = self._store.get_state(self._cell_id)
        if result is None or state is None:
            return None
        temp = state.estimates.get("temperature")
        temp_mean = temp.mean if temp else 0.0
        temp_var = temp.variance if temp else 0.0
        dominant = max(result.posterior, key=lambda k: result.posterior[k], default="baseline")
        prev_temp = prev["temp_mean"] if prev else temp_mean

        # A new decision report only when the board re-convened this tick.
        report = result.report
        new_report = report.model_dump(mode="json") if report and report.report_id != self._last_report_id else None
        if report is not None:
            self._last_report_id = report.report_id

        return {
            "tick": tick,
            "cell": CELL_LABEL,
            "cell_id": self._cell_id,
            "ts": datetime.now(UTC).isoformat(),
            "risk": result.risk_score,
            "prev_risk": prev["risk"] if prev else None,
            "band": result.risk_band.value,
            "confidence": result.confidence,
            "driver": _DRIVER_LABELS.get(dominant, dominant),
            "temp_mean": temp_mean,
            "temp_variance": temp_var,
            "temp_delta": temp_mean - prev_temp,
            "posterior": dict(result.posterior),
            "events": [_event_view(e) for e in events],
            "report_id": report.report_id if report else None,
            "report": new_report,
        }


class LiveStreamBroadcaster:
    """Run ONE :class:`LiveClimateStream` in the background and fan its frames out to N viewers.

    The expensive pipeline (Kalman → Bayesian → Monte Carlo → decision board) runs **exactly
    once** regardless of how many SSE clients are connected. Each subscriber is a lightweight
    bounded queue, not a new compute loop — so 1,000 dashboards open at once means one pipeline
    feeding 1,000 queues, not 1,000 concurrent Monte Carlo engines.

    Started/stopped from the FastAPI lifespan. The producer never blocks on a slow client: a
    full subscriber queue drops its oldest frame, so one stalled browser can't back-pressure the
    single global loop or any other viewer.
    """

    def __init__(self, stream: LiveClimateStream, *, tick_seconds: float = 1.5) -> None:
        self._stream = stream
        self._tick_seconds = tick_seconds
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._latest: dict[str, Any] | None = None
        self._task: asyncio.Task[None] | None = None

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
        """The single producer: drive the pipeline forever, broadcasting each frame."""
        async for frame in self._stream.frames(tick_seconds=self._tick_seconds):
            self._latest = frame
            for queue in list(self._subscribers):
                if queue.full():  # slow consumer — drop its oldest, never stall the producer
                    with suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                queue.put_nowait(frame)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        """Yield frames to one viewer; the newest frame is delivered immediately on connect."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=8)
        if self._latest is not None:
            queue.put_nowait(self._latest)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


def _event_view(event: GlobalEvent) -> dict[str, Any]:
    """A compact, display-ready view of a raw event for the rolling event feed."""
    obs = event.to_observation()
    return {
        "event_id": event.event_id,
        "source": obs.source,
        "variable": obs.variable,
        "value": round(obs.value, 3),
        "observed_at": obs.observed_at.isoformat(),
    }
