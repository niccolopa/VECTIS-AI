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
        "temp_anomaly_c", "humidity_pct", "wind_speed_kmh", "drought_index", "precipitation_mm",
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

    assert len(batch) == 5  # temp/humidity/wind/drought/precip; dead feed contributes nothing, no crash


def test_data_source_defaults_to_synthetic_before_any_fetch() -> None:
    """The safe, honest default: unproven means synthetic, never an assumed-live claim."""
    conn = _Probe(client=_client(httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
    assert conn.last_data_source == "synthetic_fallback"


def test_live_fetch_marks_data_source_live_and_stamps_every_event() -> None:
    """A genuine 200 → last_data_source='live', stamped onto each collected event."""
    body = {"current": {"temperature_2m": 30.0, "relative_humidity_2m": 25.0, "wind_speed_10m": 18.0}}
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    conn = WeatherAPIConnector(base_url="http://test/v1/forecast", client=client, sleep=lambda _: None)

    events = conn.collect()
    assert conn.last_data_source == "live"
    assert events and all(e.data_source == "live" for e in events)


def test_outage_marks_data_source_synthetic_and_stamps_the_fallback() -> None:
    """A keyless feed that can't reach the network serves the offline fallback, labeled synthetic."""
    client = _client(httpx.MockTransport(lambda r: httpx.Response(503)))
    conn = WeatherAPIConnector(
        base_url="http://test/v1/forecast", client=client, max_retries=2, sleep=lambda _: None
    )

    events = conn.collect()
    assert conn.last_data_source == "synthetic_fallback"
    assert events and all(e.data_source == "synthetic_fallback" for e in events)


def test_firms_is_credential_gated_not_network_gated() -> None:
    """No MAP_KEY + no gateway → synthetic every poll, regardless of the network; a key → live."""
    from vectis.realtime.connectors.firms import _FIRMS_UPSTREAM, FirmsConnector

    no_key = FirmsConnector(api_key="", base_url=_FIRMS_UPSTREAM, sleep=lambda _: None)
    events = no_key.collect()
    assert no_key.last_data_source == "synthetic_fallback"
    assert events and all(e.data_source == "synthetic_fallback" for e in events)

    # With a key, a successful fetch is live. FIRMS reads CSV via get_text.
    csv = "latitude,longitude,frp,confidence\n37.0,-120.0,14.2,80\n"
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, text=csv)))
    keyed = FirmsConnector(
        api_key="REAL_KEY", base_url=_FIRMS_UPSTREAM, client=client, sleep=lambda _: None
    )
    keyed_events = keyed.collect()
    assert keyed.last_data_source == "live"
    assert keyed_events and all(e.data_source == "live" for e in keyed_events)


def test_gdacs_skips_non_point_geometries_instead_of_crashing() -> None:
    """Real GDACS responses mix Point alerts with Polygon/MultiPoint geometries
    (nested coordinate lists) — those must be skipped, never crash the poll cycle
    (a normalize error would kill every other feed in the same cycle)."""
    from vectis.realtime.connectors.gdacs import GdacsConnector

    conn = GdacsConnector(base_url="http://x")
    events = conn.normalize(
        {
            "features": [
                {"geometry": {"coordinates": [120.9, 14.6]},
                 "properties": {"eventtype": "TC", "alertlevel": "Red"}},
                {"geometry": {"coordinates": [[[10.0, 20.0], [11.0, 21.0]]]},  # Polygon
                 "properties": {"eventtype": "FL", "alertlevel": "Orange"}},
                {"geometry": {"coordinates": [[30.0, 40.0], [31.0, 41.0]]},  # MultiPoint
                 "properties": {"eventtype": "DR", "alertlevel": "Green"}},
            ]
        }
    )
    assert len(events) == 1  # only the honest point alert survives
    assert events[0].location.lat == 14.6
