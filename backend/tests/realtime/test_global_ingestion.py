"""Session 31 — the global ingestion proof.

Drives all four real connectors (weather, FIRMS, USGS, GDACS) with recorded fixture
responses over one shared ``httpx.MockTransport`` — no live network, deterministic in CI.
Asserts a mixed poll cycle lands events on multiple distinct H3 cells across multiple
continents, that a dead FIRMS feed degrades without stalling the others, and that GDACS's
mixed hazard types survive end to end into ``GlobalObservation``.

The one test that would touch the real internet is gated behind ``VECTIS_LIVE_TESTS`` so CI
stays offline and deterministic.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import httpx
import pytest

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.connectors.firms import FirmsConnector
from vectis.realtime.connectors.gdacs import GdacsConnector
from vectis.realtime.connectors.usgs import UsgsQuakeConnector
from vectis.realtime.connectors.weather import WeatherAPIConnector
from vectis.realtime.events.base import GeoPoint
from vectis.realtime.ingestion.global_feeds import build_global_ingestion_manager, ingest_into
from vectis.realtime.state.cell_id import assign_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore

# ── recorded fixtures — real-shaped responses at real coordinates on four continents ──

_FIRMS_CSV = (
    "latitude,longitude,acq_date,acq_time,confidence,frp,daynight\n"
    "37.5,-120.5,2026-07-01,1830,h,14.2,D\n"   # California, US
    "-9.5,-62.0,2026-07-01,1700,n,21.0,D\n"    # Rondônia, BR
    "-33.4,150.3,2026-07-01,0300,l,8.0,N\n"    # New South Wales, AU
)
_USGS_JSON = {
    "features": [
        {"geometry": {"coordinates": [142.4, 38.3, 24.0]},
         "properties": {"mag": 5.8, "time": 1_751_362_200_000, "place": "off Honshu"}},
        {"geometry": {"coordinates": [-70.6, -33.4, 60.0]},
         "properties": {"mag": 5.2, "time": 1_751_362_200_000, "place": "Chile"}},
    ]
}
_GDACS_JSON = {
    "features": [
        {"geometry": {"coordinates": [120.9, 14.6]},
         "properties": {"eventtype": "TC", "alertlevel": "Red", "eventname": "Typhoon X"}},
        {"geometry": {"coordinates": [90.4, 23.8]},
         "properties": {"eventtype": "FL", "alertlevel": "Orange"}},
        {"geometry": {"coordinates": [142.4, 38.3]},
         "properties": {"eventtype": "TS", "alertlevel": "Red"}},
        {"geometry": {"coordinates": [-91.1, -0.8]},
         "properties": {"eventtype": "VO", "alertlevel": "Orange"}},
    ]
}
_WEATHER_JSON = {"current": {"temperature_2m": 30.0, "relative_humidity_2m": 20.0, "wind_speed_10m": 18.0}}


def _dispatch(request: httpx.Request, *, firms_status: int = 200) -> httpx.Response:
    path = request.url.path
    if "/api/area/csv/" in path:
        if firms_status != 200:
            return httpx.Response(firms_status)
        return httpx.Response(200, text=_FIRMS_CSV)
    if "/earthquakes/feed/" in path:
        return httpx.Response(200, json=_USGS_JSON)
    if "/gdacsapi/" in path:
        return httpx.Response(200, json=_GDACS_JSON)
    if "/v1/forecast" in path:
        return httpx.Response(200, json=_WEATHER_JSON)
    return httpx.Response(404)


_Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: _Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def _connectors(handler: _Handler) -> list[BaseAPIConnector]:
    client = _client(handler)
    noop: Callable[[float], None] = lambda _: None  # noqa: E731 - one-liner is clearer here
    return [
        WeatherAPIConnector(
            base_url="http://test/v1/forecast",
            location=GeoPoint(lat=37.0, lon=-120.0), client=client, sleep=noop,
        ),
        FirmsConnector(api_key="TESTKEY", base_url="http://test", client=client, sleep=noop),
        UsgsQuakeConnector(base_url="http://test", client=client, sleep=noop),
        GdacsConnector(base_url="http://test", client=client, sleep=noop),
    ]


def test_mixed_cycle_spans_distinct_cells_on_multiple_continents() -> None:
    manager = build_global_ingestion_manager(_connectors(_dispatch))
    store: EvictingStateStore[WorldCellState] = EvictingStateStore(MemoryStateStore())

    events = ingest_into(manager, store)
    cells = {e.to_observation().cell_id for e in events}

    # Four continents' worth of real detections resolve to four distinct H3 cells.
    california = assign_cell_id(37.5, -120.5)
    japan = assign_cell_id(38.3, 142.4)
    brazil = assign_cell_id(-9.5, -62.0)
    bangladesh = assign_cell_id(23.8, 90.4)
    assert {california, japan, brazil, bangladesh} <= cells
    assert california != japan != brazil  # not collapsed onto one demo coordinate

    assert len(cells) >= 6  # weather cell + fires + quakes + alerts, spread worldwide
    # Every distinct location became a live cell in the sparse global store.
    assert store.active_cells == len(cells)


def test_dead_firms_feed_degrades_without_stalling_the_others() -> None:
    """A dead FIRMS feed must not raise or stall — the other three keep delivering."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _dispatch(request, firms_status=500)  # FIRMS down all cycle

    events = build_global_ingestion_manager(_connectors(handler)).poll_once()
    by_source: dict[str, int] = {}
    for e in events:
        by_source[e.source] = by_source.get(e.source, 0) + 1

    # The three healthy feeds still delivered their live events...
    assert by_source.get("usgs_quake", 0) == 2
    assert by_source.get("gdacs", 0) == 4
    assert by_source.get("weather_api", 0) == 4
    # ...and FIRMS degraded cleanly to its offline fallback rather than crashing the sweep.
    assert by_source.get("nasa_firms", 0) > 0


def test_gdacs_mixed_hazards_preserved_into_observations() -> None:
    gdacs = GdacsConnector(base_url="http://test", client=_client(_dispatch), sleep=lambda _: None)
    variables = {e.to_observation().variable for e in gdacs.collect()}
    assert variables == {
        "cyclone_alert_level", "flood_alert_level", "tsunami_alert_level", "volcano_alert_level",
    }


@pytest.mark.skipif(
    not os.getenv("VECTIS_LIVE_TESTS"),
    reason="hits the real USGS feed — opt in with VECTIS_LIVE_TESTS=1 (CI stays offline)",
)
def test_live_usgs_feed_returns_real_quakes() -> None:  # pragma: no cover - network-gated
    events = UsgsQuakeConnector().collect()
    assert events, "expected at least one live M4.5+ quake in the past day"
    assert all(-90 <= e.location.lat <= 90 for e in events)
