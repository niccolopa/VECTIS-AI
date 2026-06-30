"""Session 17 — ingestion layer behavior: retry, normalization, resilience.

Drives the HTTP layer with an ``httpx.MockTransport`` (no sockets, no extra dep) and
injects a no-op ``sleep`` so backoff doesn't actually wait.
"""

from __future__ import annotations

import httpx
import pytest

from vectis.realtime.connectors.base import BaseAPIConnector, ConnectorError
from vectis.realtime.connectors.weather import WeatherAPIConnector
from vectis.realtime.events.base import GeoPoint, GlobalEvent, GlobalObservation
from vectis.realtime.ingestion.manager import IngestionManager


def _client(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=transport, base_url="http://test")


class _Probe(BaseAPIConnector):
    """Minimal concrete connector that just returns the fetched JSON as one event."""

    source = "probe"

    def fetch(self):
        return self.get_json("/data")

    def normalize(self, raw):
        return [GlobalEvent(source=self.source, location=GeoPoint(lat=0, lon=0), payload=raw)]


def test_retries_500_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    conn = _Probe(client=_client(httpx.MockTransport(handler)), sleep=lambda _: None)
    events = conn.collect()

    assert calls["n"] == 2  # one retry after the 500
    assert events[0].payload == {"ok": True}


def test_client_error_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404)

    conn = _Probe(client=_client(httpx.MockTransport(handler)), sleep=lambda _: None)
    with pytest.raises(ConnectorError):
        conn.fetch()
    assert calls["n"] == 1  # 4xx fails fast


def test_persistent_outage_degrades_gracefully() -> None:
    """A feed down for the whole window logs and returns [] — never crashes the sweep."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    conn = _Probe(client=_client(httpx.MockTransport(handler)), max_retries=3, sleep=lambda _: None)
    assert conn.collect() == []


def test_raw_json_normalizes_into_observations() -> None:
    raw = {"temperature": 34, "humidity": 20, "wind": 25}
    conn = WeatherAPIConnector(sleep=lambda _: None)  # offline mode, but normalize raw directly

    events = conn.normalize(raw)
    obs = [e.to_observation() for e in events]

    assert {o.variable for o in obs} == {"temp_anomaly_c", "humidity_pct", "wind_speed_kmh"}
    assert all(isinstance(o, GlobalObservation) for o in obs)
    temp = next(o for o in obs if o.variable == "temp_anomaly_c")
    assert temp.value == 34.0 and temp.source == "weather_api"


def test_open_meteo_response_is_fetched_and_normalized() -> None:
    """A live Open-Meteo ``current`` block normalizes to temp/humidity/wind/drought."""
    body = {"current": {"temperature_2m": 30.0, "relative_humidity_2m": 25.0, "wind_speed_10m": 18.0}}
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    conn = WeatherAPIConnector(base_url="http://test/v1/forecast", client=client, sleep=lambda _: None)

    obs = {o.variable: o.value for o in (e.to_observation() for e in conn.collect())}

    assert obs == {"temp_anomaly_c": 30.0, "humidity_pct": 25.0, "wind_speed_kmh": 18.0, "drought_index": 0.75}


def test_open_meteo_outage_falls_back_to_offline_reading() -> None:
    """No network → the weather feed degrades to a synthetic reading, never []  or a crash."""
    client = _client(httpx.MockTransport(lambda r: httpx.Response(503)))
    conn = WeatherAPIConnector(base_url="http://test/v1/forecast", client=client, max_retries=2, sleep=lambda _: None)

    events = conn.collect()
    assert {e.to_observation().variable for e in events} == {
        "temp_anomaly_c", "humidity_pct", "wind_speed_kmh", "drought_index",
    }


def test_manager_merges_and_survives_a_dead_feed() -> None:
    good = WeatherAPIConnector(base_url=None, sleep=lambda _: None)  # forced offline synthetic reading

    dead = _Probe(
        client=_client(httpx.MockTransport(lambda r: httpx.Response(500))),
        max_retries=2,
        sleep=lambda _: None,
    )

    mgr = IngestionManager([good, dead], sleep=lambda _: None)
    batch = list(mgr.run(interval=0, max_cycles=1))

    assert len(batch) == 4  # temp/humidity/wind/drought; dead feed contributes nothing, no crash
