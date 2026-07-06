"""Global ingestion broadcast — one worldwide feed loop fanned out to every terminal viewer.

Also home to the offline oscillating mock connectors (`OscillatingWeatherConnector`,
`GlobalSatelliteConnector`) the CLI demo (`scripts/demo_v3_live`) and tests inject for
deterministic, network-free runs: pure trig (no RNG), so the synthesized fire season
rises *and* falls reproducibly across viewers and test runs.
"""

from __future__ import annotations

import asyncio
import math
from collections import deque
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from vectis.core.logging import get_logger
from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.connectors.satellite import SatelliteAPIConnector
from vectis.realtime.connectors.weather import WeatherAPIConnector
from vectis.realtime.events.base import GlobalEvent
from vectis.realtime.ingestion.global_feeds import build_global_ingestion_manager, ingest_into
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import StateStore

logger = get_logger(__name__)

# Open-Meteo refreshes hourly, so polling every few seconds just re-reads the same value.
# Poll at a realistic cadence: often enough to feel live, rare enough not to hammer the API.
LIVE_TICK_SECONDS = 30.0


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
        # Drought is normalized by the base connector (in _VARIABLE_MAP), so just emit the key.
        return {
            "temperature": _wave(t, base=22.5, amp=5.0, period=11.0, ripple=1.2),
            # phase=π → dry when hot
            "humidity": max(8.0, _wave(t, base=45.0, amp=15.0, period=11.0, phase=math.pi, ripple=3.0)),
            "wind": max(0.0, _wave(t, base=15.0, amp=8.0, period=8.0, phase=1.0, ripple=2.0)),
            "drought": min(0.95, max(0.10, _wave(t, base=0.40, amp=0.20, period=17.0))),
        }


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


class GlobalIngestionBroadcaster:
    """One worldwide ingestion loop, fanned out to every terminal viewer (Session 37).

    Generalizes the Session-24 single-region transport to global scope. Each tick polls
    the four Session-31 planetary feeds (Open-Meteo weather, NASA FIRMS, USGS quakes,
    GDACS alerts) **once** and folds every event into the shared tile store at its real
    H3 cell — so the Tier-0 screen, the tile endpoint, and every viewport-scoped SSE
    stream all track the same live world. Subscribers receive each tick's *global*
    event batch (display-ready views, the ticker's tape); which cells a viewer renders
    is its viewport's business, resolved per connection at the API layer.

    Session 38 (shared broadcast pipeline) replaces the per-connection viewport
    screening layered on top of this; the expensive part here — network polling and
    state writes — already happens exactly once regardless of viewer count.
    """

    def __init__(
        self,
        store: StateStore[WorldCellState],
        *,
        manager: IngestionManager | None = None,
        tick_seconds: float = LIVE_TICK_SECONDS,
        max_recent_events: int = 100,
    ) -> None:
        self._store = store
        self._manager = manager or build_global_ingestion_manager()
        self._tick_seconds = tick_seconds
        # Newest-first backlog so a fresh terminal shows the tape immediately on connect.
        self._recent: deque[dict[str, Any]] = deque(maxlen=max_recent_events)
        self._subscribers: set[asyncio.Queue[list[dict[str, Any]]]] = set()
        self._task: asyncio.Task[None] | None = None

    @property
    def connectors(self) -> list[BaseAPIConnector]:
        """The active planetary feeds — read-only, for per-connector live/synthetic status."""
        return self._manager.connectors

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def poll_once(self) -> list[dict[str, Any]]:
        """One synchronous ingestion cycle: poll every feed into the store; return views.

        The loop's unit of work, exposed so tests (and a future scheduler) can drive
        ticks deterministically without the background task.
        """
        views = [_event_view(e) for e in ingest_into(self._manager, self._store)]
        for view in reversed(views):
            self._recent.appendleft(view)
        return views

    async def _run(self) -> None:
        while True:
            try:
                views = await asyncio.to_thread(self.poll_once)
            except Exception:
                # One bad upstream response must not silently kill the planet's
                # ingestion forever — log it, skip the tick, poll again.
                logger.exception("[ERROR] global ingestion cycle failed; retrying next tick")
                views = []
            self.publish(views)
            await asyncio.sleep(self._tick_seconds)

    def publish(self, views: list[dict[str, Any]]) -> None:
        """Fan one tick's event views out to every subscriber (never stalling on one).

        Exposed (Session 38) so the shared compute loop can own the tick — polling and
        computing in one cycle — while this broadcaster keeps serving its subscribers.
        """
        for queue in list(self._subscribers):
            if queue.full():  # slow consumer — drop its oldest batch, never stall
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(views)

    async def subscribe(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield event batches to one viewer, starting with the recent backlog.

        The first batch is delivered immediately (even if empty) so a connecting
        terminal paints its viewport without waiting out a tick interval.
        """
        queue: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue(maxsize=8)
        queue.put_nowait(list(self._recent))
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
        # Per-event honesty: was this genuinely fetched live, or a synthetic fallback?
        "data_source": event.data_source,
    }
