"""Session 34 Step 2 — the spatial-temporal join, negatives, and dataset staging."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import h3
import pytest

from vectis.calibration.data.dataset import (
    DATASET_COLUMNS,
    build_dataset,
    read_dataset,
    region_cells,
    write_dataset,
)
from vectis.calibration.data.era5 import DailyWeather
from vectis.data.regions import CALIFORNIA
from vectis.realtime.state.cell_id import assign_cell_id

_START, _END = date(2020, 8, 1), date(2020, 8, 10)
_FIRE_A = (37.4523, -119.8811)  # two detections same cell-day → one positive
_FIRE_B = (38.9101, -120.7203)


class FakeFirms:
    def fetch_detections(self, bbox, start, end):
        stamp = datetime(2020, 8, 3, 9, 12, tzinfo=UTC)
        return [
            {"latitude": _FIRE_A[0], "longitude": _FIRE_A[1], "frp": 12.0, "confidence": 70.0, "observed_at": stamp},
            {"latitude": _FIRE_A[0], "longitude": _FIRE_A[1], "frp": 8.0, "confidence": 95.0, "observed_at": stamp},
            {"latitude": _FIRE_B[0], "longitude": _FIRE_B[1], "frp": 30.0, "confidence": 70.0, "observed_at": datetime(2020, 8, 7, 21, 0, tzinfo=UTC)},
            # Outside the window and timestamp-less: neither can be a dated label.
            {"latitude": 37.0, "longitude": -120.0, "frp": 5.0, "confidence": 70.0, "observed_at": datetime(2020, 7, 1, tzinfo=UTC)},
            {"latitude": 37.1, "longitude": -120.1, "frp": 5.0, "confidence": 70.0, "observed_at": None},
        ]


class FakeEra5:
    """Deterministic full-coverage daily series: 30 °C max temp, 20 km/h wind, 1 mm/day."""

    def __init__(self, hole: tuple[float, float] | None = None) -> None:
        self.hole = hole  # centroid whose label-window days are missing (data gap)
        self.calls: list[tuple[int, date, date]] = []

    def fetch_daily(self, points, start, end):
        self.calls.append((len(points), start, end))
        out = []
        for lat, _lon in points:
            days = []
            for i in range((end - start).days + 1):
                day = start + timedelta(days=i)
                if self.hole and abs(lat - self.hole[0]) < 1e-6 and day >= _START:
                    continue  # gap: lead-in exists, labeled days missing
                days.append(DailyWeather(day, temp_max_c=30.0, rh_min_pct=25.0, wind_max_kmh=20.0, precip_mm=1.0))
            out.append(days)
        return out


def test_join_labels_positives_on_their_cell_day_and_dedupes() -> None:
    ds = build_dataset(
        CALIFORNIA, _START, _END, firms=FakeFirms(), era5=FakeEra5(),
        negatives_per_positive=2.0, seed=7,
    )
    fires = {(r.cell_id, r.day) for r in ds.rows if r.fire}
    assert fires == {
        (assign_cell_id(*_FIRE_A), date(2020, 8, 3)),
        (assign_cell_id(*_FIRE_B), date(2020, 8, 7)),
    }
    assert ds.manifest["detections_fetched"] == 5
    assert ds.manifest["positive_cell_days"] == 2  # dedup + window/timestamp filtering


def test_negatives_come_from_the_same_region_window_and_never_overlap_positives() -> None:
    ds = build_dataset(
        CALIFORNIA, _START, _END, firms=FakeFirms(), era5=FakeEra5(),
        negatives_per_positive=3.0, seed=7,
    )
    negatives = [r for r in ds.rows if not r.fire]
    region = set(region_cells(CALIFORNIA))
    assert len(negatives) == 6  # 3.0 × 2 positives
    for r in negatives:
        assert r.cell_id in region
        assert _START <= r.day <= _END
    assert not {(r.cell_id, r.day) for r in negatives} & {(r.cell_id, r.day) for r in ds.rows if r.fire}


def test_negative_sampling_is_deterministic_under_the_seed() -> None:
    kw = {"firms": FakeFirms(), "era5": FakeEra5(), "negatives_per_positive": 2.0}
    a = build_dataset(CALIFORNIA, _START, _END, seed=34, **kw)
    b = build_dataset(CALIFORNIA, _START, _END, seed=34, **kw)
    assert [(r.cell_id, r.day) for r in a.rows] == [(r.cell_id, r.day) for r in b.rows]


def test_features_use_the_serve_time_transforms() -> None:
    era5 = FakeEra5()
    ds = build_dataset(
        CALIFORNIA, _START, _END, firms=FakeFirms(), era5=era5,
        negatives_per_positive=1.0, seed=7,
    )
    row = ds.rows[0]
    # Same ~22 °C climatology the live bridge subtracts: 30 − 22 = 8.
    assert row.temp_anomaly_c == pytest.approx(8.0)
    assert row.wind_speed_kmh == pytest.approx(20.0)
    # Uniform precipitation everywhere → every trail equals the regional mean → 0 %.
    assert row.rainfall_anomaly_pct == pytest.approx(0.0)
    # The ERA5 fetch reached back 30 days before the window for the rainfall trail.
    (n_points, w_start, w_end), = era5.calls
    assert w_start == _START - timedelta(days=30) and w_end == _END


def test_cell_days_with_missing_weather_are_dropped_and_counted() -> None:
    hole_centroid = h3.cell_to_latlng(assign_cell_id(*_FIRE_A))
    ds = build_dataset(
        CALIFORNIA, _START, _END, firms=FakeFirms(), era5=FakeEra5(hole=hole_centroid),
        negatives_per_positive=1.0, seed=7,
    )
    assert ds.manifest["rows_dropped_missing_weather"] >= 1
    assert all(r.cell_id != assign_cell_id(*_FIRE_A) for r in ds.rows)


def test_write_then_read_roundtrips_with_manifest(tmp_path) -> None:
    ds = build_dataset(
        CALIFORNIA, _START, _END, firms=FakeFirms(), era5=FakeEra5(),
        negatives_per_positive=2.0, seed=7,
    )
    path = write_dataset(ds, tmp_path)
    assert path.name == "wildfire_california_2020-08-01_2020-08-10.csv"
    assert path.parent == tmp_path / "processed" / "calibration"
    manifest = path.with_name(path.stem + ".manifest.json")
    assert manifest.exists()

    back = read_dataset(path)
    assert len(back) == len(ds.rows)
    assert {(r.cell_id, r.day, r.fire) for r in back} == {
        (r.cell_id, r.day, r.fire) for r in ds.rows
    }
    with path.open(encoding="utf-8") as fh:
        assert fh.readline().strip() == ",".join(DATASET_COLUMNS)


def test_region_cells_cover_the_bbox_at_resolution_5() -> None:
    cells = region_cells(CALIFORNIA)
    assert len(cells) > 400  # the 4°×4° California bbox is ~580 res-5 hexes
    assert all(h3.get_resolution(c) == 5 for c in cells[:10])
