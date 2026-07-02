"""Session 34 Step 1 — the historical acquisition clients, against real API shapes.

No live network anywhere: every payload below is shaped exactly like the real API's
response (FIRMS VIIRS_SNPP_SP area CSV; Open-Meteo ``/v1/era5`` archive JSON), served
through ``httpx.MockTransport`` — the same offline pattern as the Session-31 connectors.
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from vectis.calibration.data.base import CalibrationDataError
from vectis.calibration.data.era5 import Era5Client, _aggregate_daily
from vectis.calibration.data.firms_archive import FirmsArchiveClient
from vectis.data.regions import CALIFORNIA

# Real VIIRS_SNPP_SP column layout (standard-processing archive product).
_FIRMS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight,type\n"
    "37.4523,-119.8811,331.2,0.39,0.36,2020-08-17,0912,N,VIIRS,n,2,290.1,12.6,D,0\n"
    "38.1201,-120.3355,345.0,0.41,0.37,2020-08-17,0912,N,VIIRS,h,2,301.7,45.3,D,0\n"
)


def _firms_client(handler, api_key="TESTKEY"):
    return FirmsArchiveClient(
        api_key=api_key,
        base_url="https://firms.modaps.eosdis.nasa.gov",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )


def test_firms_archive_parses_real_shaped_csv_with_key_product_bbox_in_path() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=_FIRMS_CSV)

    dets = _firms_client(handler).fetch_detections(
        CALIFORNIA.bbox, date(2020, 8, 17), date(2020, 8, 17)
    )
    assert len(dets) == 2
    assert dets[0]["latitude"] == pytest.approx(37.4523)
    assert dets[0]["confidence"] == 70.0  # VIIRS 'n' letter → midpoint, live-parser reuse
    assert dets[0]["observed_at"] is not None and dets[0]["observed_at"].hour == 9
    # One request: key, archive product, W,S,E,N bbox, day range 1, start date — in path.
    assert seen == [
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/TESTKEY/VIIRS_SNPP_SP/"
        "-122.0,36.0,-118.0,40.0/1/2020-08-17"
    ]


def test_firms_archive_chunks_long_windows_at_the_10_day_api_limit() -> None:
    starts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        parts = request.url.path.rstrip("/").split("/")
        starts.append(f"{parts[-1]}:{parts[-2]}")  # start-date:day-range
        return httpx.Response(200, text=_FIRMS_CSV)

    dets = _firms_client(handler).fetch_detections(
        CALIFORNIA.bbox, date(2020, 6, 1), date(2020, 6, 25)
    )
    # 25 days → 10 + 10 + 5, consecutive and non-overlapping.
    assert starts == ["2020-06-01:10", "2020-06-11:10", "2020-06-21:5"]
    assert len(dets) == 6  # 2 rows per chunk, all kept


def test_firms_archive_without_credentials_raises_with_instructions() -> None:
    client = _firms_client(lambda req: httpx.Response(200, text=""), api_key="")
    with pytest.raises(CalibrationDataError, match="VECTIS_FIRMS_API_KEY"):
        client.fetch_detections(CALIFORNIA.bbox, date(2020, 6, 1), date(2020, 6, 2))


# ── ERA5 via the keyless Open-Meteo archive ──────────────────────────────────────────
def _era5_payload() -> dict:
    """Two full days of hourly data, shaped exactly like /v1/era5 output."""
    times, temps, rh, wind, precip = [], [], [], [], []
    for day in ("2020-08-01", "2020-08-02"):
        for hour in range(24):
            times.append(f"{day}T{hour:02d}:00")
            temps.append(20.0 + hour * 0.5)  # daily max = 31.5
            rh.append(60.0 - hour)  # daily min = 37.0
            wind.append(10.0 + (hour % 5))  # daily max = 14.0
            precip.append(0.1)  # daily sum = 2.4
    return {
        "latitude": 37.0,
        "longitude": -120.0,
        "timezone": "UTC",
        "hourly_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "relative_humidity_2m": rh,
            "wind_speed_10m": wind,
            "precipitation": precip,
        },
    }


def test_era5_daily_aggregation_from_real_shaped_hourly_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/era5"
        params = dict(request.url.params)
        assert params["hourly"].startswith("temperature_2m")
        assert params["timezone"] == "UTC"
        # Two locations requested → the API answers with a JSON array.
        return httpx.Response(200, json=[_era5_payload(), _era5_payload()])

    client = Era5Client(
        base_url="https://archive-api.open-meteo.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    per_point = client.fetch_daily(
        [(37.0, -120.0), (38.0, -121.0)], date(2020, 8, 1), date(2020, 8, 2)
    )
    assert len(per_point) == 2
    d1, d2 = per_point[0]
    assert d1.day == date(2020, 8, 1) and d2.day == date(2020, 8, 2)
    assert d1.temp_max_c == pytest.approx(31.5)
    assert d1.rh_min_pct == pytest.approx(37.0)
    assert d1.wind_max_kmh == pytest.approx(14.0)
    assert d1.precip_mm == pytest.approx(2.4)


def test_era5_single_location_dict_response_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_era5_payload())  # dict, not list

    client = Era5Client(
        base_url="https://archive-api.open-meteo.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    per_point = client.fetch_daily([(37.0, -120.0)], date(2020, 8, 1), date(2020, 8, 2))
    assert len(per_point) == 1 and len(per_point[0]) == 2


def test_era5_batches_many_points_into_multiple_requests() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        n = len(dict(request.url.params)["latitude"].split(","))
        calls.append(n)
        return httpx.Response(200, json=json.loads(json.dumps([_era5_payload()] * n)))

    client = Era5Client(
        base_url="https://archive-api.open-meteo.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    points = [(36.0 + i * 0.01, -120.0) for i in range(120)]
    per_point = client.fetch_daily(points, date(2020, 8, 1), date(2020, 8, 2))
    assert calls == [50, 50, 20]
    assert len(per_point) == 120


def test_era5_null_gaps_are_skipped_never_invented() -> None:
    hourly = {
        "time": ["2020-08-01T00:00", "2020-08-01T01:00", "2020-08-02T00:00"],
        "temperature_2m": [25.0, None, None],  # day 2 has no temperature at all
        "relative_humidity_2m": [40.0, None, 50.0],
        "wind_speed_10m": [12.0, None, 8.0],
        "precipitation": [0.0, None, 1.0],
    }
    days = _aggregate_daily(hourly)
    # Day 2 is a hole (no temperature), not a fabricated zero-temperature day.
    assert [d.day.isoformat() for d in days] == ["2020-08-01"]
    assert days[0].temp_max_c == 25.0
