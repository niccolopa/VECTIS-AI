"""Session 25 — the two reality-gap fixes the audit demanded.

1. The Kalman estimate must actually drive the Monte Carlo overlay (no silently-dropped
   variables from the ``temperature`` vs ``temp_anomaly_c`` mismatch).
2. The satellite connector must parse a real NASA FIRMS CSV response into observations,
   while staying offline-safe with no API key.
"""

from __future__ import annotations

import httpx

from vectis.realtime.connectors.satellite import SatelliteAPIConnector
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState, VariableEstimate
from vectis.realtime.pipeline import KALMAN_TO_WORLD, build_default_pipeline


def _client(body: str, *, status: int = 200) -> httpx.Client:
    transport = httpx.MockTransport(lambda _req: httpx.Response(status, text=body))
    return httpx.Client(transport=transport, base_url="http://test")


# ── 1. Kalman → Monte Carlo overlay ────────────────────────────────────────────
def test_kalman_estimate_drives_monte_carlo_overlay() -> None:
    """Every mapped Kalman variable lands in the WorldState — none silently dropped."""
    pipe = build_default_pipeline(n_iterations=1)
    base = {v.name: v.value for v in pipe._base_state.variables}

    # A live Kalman belief: a hot, windy cell.
    state = KalmanCellState(
        cell_id="44.4,8.9",
        estimates={
            "temperature": VariableEstimate(mean=40.0, variance=1.0),
            "wind_speed_kmh": VariableEstimate(mean=50.0, variance=1.0),
        },
    )
    overlaid = {v.name: v.value for v in pipe._overlay_state(state).variables}

    # Temperature is mapped onto temp_anomaly_c with the climatology offset (not dropped).
    world_var, offset = KALMAN_TO_WORLD["temperature"]
    assert world_var == "temp_anomaly_c"
    assert overlaid["temp_anomaly_c"] == 40.0 + offset
    assert overlaid["temp_anomaly_c"] != base["temp_anomaly_c"]  # the mean actually moved it

    # Wind maps straight through.
    assert overlaid["wind_speed_kmh"] == 50.0

    # Variables with no live estimate keep their base value (not zeroed).
    assert overlaid["rainfall_anomaly_pct"] == base["rainfall_anomaly_pct"]
    assert overlaid["ignition_sources"] == base["ignition_sources"]


def test_hotter_kalman_state_yields_higher_overlaid_temperature() -> None:
    """A hotter Kalman mean must produce a hotter MC input — the link is monotonic."""
    pipe = build_default_pipeline(n_iterations=1)

    def overlaid_temp(mean: float) -> float:
        state = KalmanCellState(
            cell_id="c", estimates={"temperature": VariableEstimate(mean=mean, variance=1.0)}
        )
        target = next(v for v in pipe._overlay_state(state).variables if v.name == "temp_anomaly_c")
        return target.value

    assert overlaid_temp(38.0) > overlaid_temp(26.0)


# ── 2. NASA FIRMS connector ─────────────────────────────────────────────────────
_FIRMS_CSV = (
    "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,frp,daynight\n"
    "44.42,8.95,330.1,2026-06-30,1200,N,n,18.7,D\n"  # VIIRS letter confidence (nominal)
    "44.05,9.80,350.0,2026-06-30,1201,N,h,42.1,D\n"  # high confidence
    "not_a_number,9.0,,2026-06-30,1202,N,l,3.0,D\n"  # malformed row → skipped
)


def test_firms_csv_is_parsed_into_observations() -> None:
    conn = SatelliteAPIConnector(api_key="TEST_MAP_KEY", client=_client(_FIRMS_CSV))
    events = conn.collect()
    obs = [e.to_observation() for e in events]

    # Two good rows parsed; the malformed row is dropped, not fatal.
    assert len(obs) == 2
    assert all(o.variable == "fire_radiative_power" and o.source == "nasa_firms" for o in obs)

    frp = sorted(o.value for o in obs)
    assert frp == [18.7, 42.1]

    # Higher FIRMS confidence → smaller measurement std (a 'h' detection is trusted more).
    by_frp = {round(e.payload["frp"], 1): e for e in events}
    assert by_frp[42.1].payload["std"] < by_frp[18.7].payload["std"]


def test_firms_offline_without_key_is_clone_safe() -> None:
    """No MAP_KEY → deterministic offline detections, no network call."""
    conn = SatelliteAPIConnector(api_key="")
    events = conn.collect()
    assert len(events) == 2
    assert all(e.source == "nasa_firms" for e in events)


def test_firms_outage_degrades_gracefully() -> None:
    """A FIRMS 503 must yield [] (collect swallows it), never crash the ingestion sweep."""
    conn = SatelliteAPIConnector(
        api_key="TEST_MAP_KEY", client=_client("", status=503),
        max_retries=2, sleep=lambda _: None,
    )
    assert conn.collect() == []


if __name__ == "__main__":
    test_kalman_estimate_drives_monte_carlo_overlay()
    test_hotter_kalman_state_yields_higher_overlaid_temperature()
    test_firms_csv_is_parsed_into_observations()
    test_firms_offline_without_key_is_clone_safe()
    test_firms_outage_degrades_gracefully()
    print("ok")
