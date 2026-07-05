"""Session 41 — the per-connector live/synthetic status endpoint.

The terminal's transparency source of truth: GET /api/v1/connectors must report each
feed's REAL last-poll state, and flag the zero-credential all-synthetic case — never a
hardcoded assumption. These tests drive the connectors' last_data_source directly and
assert the endpoint (and its aggregates) reflect exactly that.
"""

from __future__ import annotations


def _set_sources(client, mapping: dict[str, str]) -> None:
    """Force each named connector's last_data_source, as a real poll would."""
    for conn in client.app.state.global_ingestion.connectors:
        if conn.source in mapping:
            conn.last_data_source = mapping[conn.source]  # type: ignore[assignment]


def test_status_reflects_actual_per_connector_data_source(client) -> None:
    _set_sources(
        client,
        {
            "weather_api": "live",
            "usgs_quake": "live",
            "gdacs": "live",
            "nasa_firms": "synthetic_fallback",  # the real state here: no MAP_KEY
        },
    )
    body = client.get("/api/v1/connectors").json()

    by_source = {c["source"]: c for c in body["connectors"]}
    assert by_source["nasa_firms"]["data_source"] == "synthetic_fallback"
    assert by_source["nasa_firms"]["label"] == "Fire"
    assert by_source["usgs_quake"]["data_source"] == "live"
    # Mixed state → not all synthetic, but something is live.
    assert body["all_synthetic"] is False
    assert body["any_live"] is True


def test_all_synthetic_flag_is_true_iff_every_feed_is_synthetic(client) -> None:
    _set_sources(
        client,
        dict.fromkeys(("weather_api", "usgs_quake", "gdacs", "nasa_firms"), "synthetic_fallback"),
    )
    body = client.get("/api/v1/connectors").json()
    assert body["all_synthetic"] is True
    assert body["any_live"] is False
    assert {c["label"] for c in body["connectors"]} == {"Weather", "Quake", "Multi-hazard", "Fire"}

    # Flip one feed live → the all-synthetic banner condition must clear.
    _set_sources(client, {"usgs_quake": "live"})
    body2 = client.get("/api/v1/connectors").json()
    assert body2["all_synthetic"] is False
    assert body2["any_live"] is True
