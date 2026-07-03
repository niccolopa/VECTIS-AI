"""Session 37 — the viewport-scoped terminal stream.

The Session-24 SSE transport generalized to global scope: one shared ingestion
broadcaster polls the planetary feeds into the tile store, and each connection's
frames carry (a) the *global* event tape and (b) only the cells visible in *its*
viewport, sourced through the screening-only tile path. Offline and deterministic:
recorded fixture responses over ``httpx.MockTransport`` (the Session-31 pattern).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import h3
import httpx

from vectis.realtime.connectors.base import BaseAPIConnector
from vectis.realtime.connectors.gdacs import GdacsConnector
from vectis.realtime.connectors.usgs import UsgsQuakeConnector
from vectis.realtime.connectors.weather import WeatherAPIConnector
from vectis.realtime.events.base import GeoPoint
from vectis.realtime.ingestion.global_feeds import build_global_ingestion_manager
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore

# ── recorded fixtures: a hot California cell + far-away detections (Japan, Manila) ──
_USGS_JSON = {
    "features": [
        {"geometry": {"coordinates": [142.4, 38.3, 24.0]},
         "properties": {"mag": 5.8, "time": 1_751_362_200_000, "place": "off Honshu"}},
    ]
}
_GDACS_JSON = {
    "features": [
        {"geometry": {"coordinates": [120.9, 14.6]},
         "properties": {"eventtype": "TC", "alertlevel": "Red", "eventname": "Typhoon X"}},
    ]
}
_WEATHER_JSON = {
    "current": {"temperature_2m": 38.0, "relative_humidity_2m": 12.0, "wind_speed_10m": 30.0}
}


def _dispatch(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if "/earthquakes/feed/" in path:
        return httpx.Response(200, json=_USGS_JSON)
    if "/gdacsapi/" in path:
        return httpx.Response(200, json=_GDACS_JSON)
    if "/v1/forecast" in path:
        return httpx.Response(200, json=_WEATHER_JSON)
    return httpx.Response(404)


def _fixture_broadcaster(
    store: MemoryStateStore[WorldCellState], **kwargs: int
) -> GlobalIngestionBroadcaster:
    client = httpx.Client(transport=httpx.MockTransport(_dispatch), base_url="http://test")
    noop: Callable[[float], None] = lambda _: None  # noqa: E731 - one-liner is clearer here
    connectors: list[BaseAPIConnector] = [
        WeatherAPIConnector(
            base_url="http://test/v1/forecast",
            location=GeoPoint(lat=37.0, lon=-120.0), client=client, sleep=noop,
        ),
        UsgsQuakeConnector(base_url="http://test", client=client, sleep=noop),
        GdacsConnector(base_url="http://test", client=client, sleep=noop),
    ]
    return GlobalIngestionBroadcaster(
        store, manager=build_global_ingestion_manager(connectors), **kwargs
    )


def test_poll_once_lands_worldwide_events_in_the_store() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    broadcaster = _fixture_broadcaster(store)

    views = broadcaster.poll_once()

    assert views, "a poll cycle should yield events"
    assert {"event_id", "source", "variable", "value", "observed_at"} <= views[0].keys()
    # California weather + Japan quake + Manila cyclone → distinct live cells.
    states = store.active_states()
    assert len(states) >= 3
    lats = {round(h3.cell_to_latlng(s.cell_id)[0]) for s in states}
    assert len(lats) >= 3  # spread across the planet, not one demo coordinate


def test_recent_backlog_is_newest_first_and_capped() -> None:
    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    broadcaster = _fixture_broadcaster(store, max_recent_events=2)

    views = broadcaster.poll_once()

    assert len(views) >= 3
    backlog = list(broadcaster._recent)
    assert len(backlog) == 2  # capped
    assert backlog == views[:2]  # the freshest batch leads


def test_subscribe_delivers_the_backlog_immediately() -> None:
    async def run() -> list[dict]:
        store: MemoryStateStore[WorldCellState] = MemoryStateStore()
        broadcaster = _fixture_broadcaster(store)
        broadcaster.poll_once()
        gen = broadcaster.subscribe()
        try:
            return await asyncio.wait_for(anext(gen), timeout=1.0)
        finally:
            await gen.aclose()

    batch = asyncio.run(run())
    assert batch, "a connecting viewer must not wait out a tick for its first batch"
    assert {e["source"] for e in batch} >= {"usgs_quake", "gdacs"}


def test_terminal_stream_frames_are_viewport_scoped_with_a_global_tape(client) -> None:
    store = client.app.state.tile_store
    client.app.state.global_ingestion = _fixture_broadcaster(store)
    client.app.state.global_ingestion.poll_once()

    # frames=1 bounds the stream server-side: with no background tick loop running in
    # tests, an unbounded SSE generator would block on its queue forever and deadlock
    # the in-process transport's close.
    with client.stream(
        "GET", "/api/v1/stream/v3/terminal",
        params={"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 8, "frames": 1},
    ) as res:
        assert res.status_code == 200
        frame = None
        for line in res.iter_lines():
            if line.startswith("data:"):
                frame = json.loads(line.split("data:", 1)[1])
                break
    assert frame is not None

    # Cells: only what the viewport sees — every center inside the requested bbox,
    # and the Japan/Manila detections are NOT rendered.
    assert frame["cells"], "the hot California cell should be screened and visible"
    for cell in frame["cells"]:
        assert 32 <= cell["lat"] <= 42 and -125 <= cell["lon"] <= -114

    # Events: the worldwide tape, not viewport-filtered.
    assert {e["source"] for e in frame["events"]} >= {"usgs_quake", "gdacs"}

    # Headline: the hottest screened score visible in the viewport.
    hottest = max(s for c in frame["cells"] for s in c["hazards"].values())
    assert frame["risk"] == hottest
    assert frame["band"] is not None
    assert frame["scope"] == {"west": -125, "south": 32, "east": -114, "north": 42, "zoom": 8}
    assert frame["resolution"] == 5  # zoom 8 → native grid resolution
