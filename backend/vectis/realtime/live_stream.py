"""Live V3 climate-risk stream — a continuously-updating frame source for the API/UI.

The terminal demo (`scripts/demo_v3_live`) renders the V3 ``ContinuousPipeline`` to
stdout. This module exposes the *same* living pipeline as a stream of JSON-serializable
**frames** so the React console can subscribe over Server-Sent Events and animate the
risk shifting in real time.

    IngestionManager(fluctuating feeds) → EventProducer → broker
        → ContinuousPipeline (Kalman → Bayesian → Monte Carlo → Decision Report)
        → frame dict  (risk · Kalman state · posterior · raw events · report id)

Offline and deterministic: no API key, no network — the mock feeds synthesize a live
fire season (readings rise *and* fall around an elevated baseline), the deterministic
engines produce every number.
"""

from __future__ import annotations

import asyncio
import math
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
from vectis.simulation.scenarios.generator import (
    WildfireScenarioGenerator,
    california_wildfire_state,
)
from vectis.simulation.schemas import SimulationConfig

logger = get_logger(__name__)

CELL_LABEL = "California_01"  # friendly name for the grid cell the California feeds map to


# ── fluctuating mock feeds — the engine of the "live" feeling ─────────────────
# Each reading is a baseline + a sine wave + a faster, incommensurate ripple, so the
# feeds rise AND fall through the moderate→severe bands instead of ramping to 100% and
# flatlining. Pure trig (no RNG) → reproducible across viewers and test runs.
def _wave(
    t: int, *, base: float, amp: float, period: float, phase: float = 0.0, ripple: float = 0.0
) -> float:
    """Baseline + a primary sine of ``period`` ticks + an optional faster ripple."""
    value = base + amp * math.sin(2 * math.pi * t / period + phase)
    if ripple:
        value += ripple * math.sin(2 * math.pi * t / 5.3 + phase * 1.7)
    return value


class OscillatingWeatherConnector(WeatherAPIConnector):
    """Offline weather feed whose readings fluctuate around an elevated fire-season baseline.

    Each ``fetch`` advances a tick and returns temperature/humidity/wind/drought that
    rise and fall on differing periods (humidity anti-correlated with temperature), so
    the live risk and confidence curves breathe up and down like a real feed rather than
    ramping to a flatline. Drought has no slot in the base weather payload, so we emit it
    as an extra normalized event.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0

    def fetch(self) -> dict[str, Any]:
        t = self._tick
        self._tick += 1
        # Baselines kept moderate: temp_anomaly_c = temperature − 22 (see KALMAN_TO_WORLD),
        # and the wildfire logistic saturates past ~+6 °C anomaly. Centering temperature near
        # 25 °C (anomaly ~3) keeps the swing inside the moderate→severe band, not pinned at 100.
        return {
            "temperature": _wave(t, base=22.5, amp=5.0, period=11.0, ripple=1.2),
            # phase=π → dry when hot
            "humidity": max(8.0, _wave(t, base=45.0, amp=15.0, period=11.0, phase=math.pi, ripple=3.0)),
            "wind": max(0.0, _wave(t, base=15.0, amp=8.0, period=8.0, phase=1.0, ripple=2.0)),
            "drought": min(0.95, max(0.10, _wave(t, base=0.40, amp=0.20, period=17.0))),
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


class GlobalSatelliteConnector(SatelliteAPIConnector):
    """Offline FIRMS-style feed: active-fire hotspots across the globe, fluctuating FRP.

    Emits detections at fixed real-world locations (incl. the headline California cell) whose
    fire-radiative-power rises and falls each poll. The worldwide spread is what the global
    map plots; the California detection feeds the headline cell's hazard signal.
    """

    # (lat, lon, place, baseline FRP) — a plausible global fire footprint. The first
    # entry is the headline California cell: its coordinates MUST match the weather
    # connector's default location so both feeds resolve to the same grid cell.
    _HOTSPOTS: tuple[tuple[float, float, str, float], ...] = (
        (37.0, -120.0, "California, US", 28.0),
        (-33.40, 150.30, "New South Wales, AU", 22.0),
        (38.50, 23.60, "Attica, GR", 18.0),
        (49.20, -123.10, "British Columbia, CA", 14.0),
        (-9.50, -62.00, "Rondônia, BR", 20.0),
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tick = 0

    def fetch(self) -> dict[str, Any]:
        t = self._tick
        self._tick += 1
        detections = [
            {
                "latitude": lat,
                "longitude": lon,
                "place": place,
                "frp": max(0.0, _wave(t, base=frp, amp=frp * 0.6, period=9.0, phase=i, ripple=frp * 0.2)),
                "confidence": 70 + int(20 * math.sin(2 * math.pi * t / 9.0 + i)),
            }
            for i, (lat, lon, place, frp) in enumerate(self._HOTSPOTS)
        ]
        return {"detections": detections}


class LiveClimateStream:
    """Wire the live California pipeline and emit one renderable frame per tick.

    Mirrors ``build_default_pipeline`` but keeps the Kalman store + ingestion manager
    references the frame builder needs (variance, raw events). The pipeline's bootstrap
    *is* the wiring — kept here, not in a script, so the API can reuse it cleanly.
    """

    def __init__(
        self,
        *,
        n_iterations: int = 8_000,
        seed: int = 7,
        region: str = "california",
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
        base_state = california_wildfire_state(region)
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

        weather = OscillatingWeatherConnector()
        satellite = GlobalSatelliteConnector()
        self._manager = IngestionManager([weather, satellite])
        self._producer = EventProducer(self._manager, broker, topic=DEFAULT_TOPIC)
        # Both feeds report at California's centroid → the same grid cell.
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
            # Worldwide active-fire detections this tick — the global map plots these.
            "hotspots": [
                {
                    "lat": e.location.lat,
                    "lon": e.location.lon,
                    "frp": round(float(e.payload["frp"]), 1),
                    "place": str(e.payload.get("place", "")),
                }
                for e in events
                if "frp" in e.payload
            ],
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
