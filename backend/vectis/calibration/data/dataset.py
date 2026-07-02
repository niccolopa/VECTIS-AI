"""Spatial-temporal join: FIRMS labels × ERA5 weather → one labeled training table.

The unit of observation is a **cell-day**: one H3 resolution-5 cell (the project's
grid unit since Session 30) on one UTC calendar day.

- **Positives**: every FIRMS detection lands on its H3 cell via the same
  :func:`assign_cell_id` the live pipeline uses; multiple detections in one cell-day
  collapse to a single ``fire=1`` label (the label is "a fire occurred here today",
  not a detection count).
- **Negatives** (without which a model cannot discriminate): cell-days drawn — with a
  seeded RNG, so the dataset is reproducible — from the *same region and window*, from
  the set of (cell, day) pairs with **no** detection. The negatives:positives ratio is
  explicit and recorded in the manifest, because it sets the base rate the fitted
  intercept absorbs.
- **Features** are built with the *same transforms the live path applies at serve time*
  (fit/serve consistency — a model fit on one feature definition and served another is
  miscalibrated by construction):

  - ``temp_anomaly_c`` = ERA5 daily max temperature − the same ~22 °C climatology the
    ``KALMAN_TO_WORLD`` bridge and the screening index subtract today.
  - ``wind_speed_kmh`` = ERA5 daily max wind (already km/h — canonical units).
  - ``rainfall_anomaly_pct`` = trailing 30-day precipitation vs. the region-window mean,
    as a % anomaly — antecedent dryness, ending the day *before* the label day so no
    same-day information leaks into the feature.
  - ``ignition_sources`` is deliberately **absent**: not observable from FIRMS/ERA5, so
    it cannot be fit from this dataset (see :mod:`vectis.calibration.fit`).

A cell-day whose ERA5 series has a hole is dropped and counted in the manifest — never
filled with an invented value.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import h3

from vectis.calibration.data.era5 import DailyWeather, Era5Client
from vectis.calibration.data.firms_archive import FirmsArchiveClient
from vectis.core.logging import get_logger
from vectis.data.regions import Region
from vectis.realtime.screening.wildfire import _CLIMATOLOGY_TEMP_C
from vectis.realtime.state.cell_id import assign_cell_id

logger = get_logger(__name__)

#: Days of antecedent precipitation the rainfall-anomaly feature integrates. The ERA5
#: fetch extends this far before the window start so the first labeled day has a full trail.
RAINFALL_TRAIL_DAYS = 30

#: Columns of the written dataset, in order — the data contract Step 3's fitter reads.
DATASET_COLUMNS = (
    "cell_id", "day", "lat", "lon",
    "temp_anomaly_c", "rainfall_anomaly_pct", "wind_speed_kmh", "fire",
)


@dataclass(frozen=True, slots=True)
class LabeledCellDay:
    """One training row: the model's serve-time features plus the FIRMS outcome label."""

    cell_id: str
    day: date
    lat: float
    lon: float
    temp_anomaly_c: float
    rainfall_anomaly_pct: float
    wind_speed_kmh: float
    fire: bool


@dataclass(frozen=True, slots=True)
class CalibrationDataset:
    """The joined table plus its provenance manifest (what, where, when, how many)."""

    rows: list[LabeledCellDay]
    manifest: dict[str, Any]


def region_cells(region: Region, resolution: int = 5) -> list[str]:
    """All H3 cells covering the region's bbox — the negative-sampling universe."""
    bb = region.bbox
    ring = [
        (bb.min_lat, bb.min_lon), (bb.min_lat, bb.max_lon),
        (bb.max_lat, bb.max_lon), (bb.max_lat, bb.min_lon),
    ]
    return sorted(h3.polygon_to_cells(h3.LatLngPoly(ring), resolution))


def build_dataset(
    region: Region,
    start: date,
    end: date,
    *,
    firms: FirmsArchiveClient,
    era5: Era5Client,
    negatives_per_positive: float = 3.0,
    seed: int = 34,
) -> CalibrationDataset:
    """Fetch, join, and label — the whole Step-1+2 pipeline for one region/window."""
    detections = firms.fetch_detections(region.bbox, start, end)

    # Positives: detection → H3 cell-day, deduplicated.
    positives: set[tuple[str, date]] = set()
    for det in detections:
        observed = det.get("observed_at")
        day = observed.date() if isinstance(observed, datetime) else None
        if day is None or not (start <= day <= end):
            continue  # a row with no timestamp cannot be a dated label — drop it
        positives.add((assign_cell_id(det["latitude"], det["longitude"]), day))

    # Negatives: seeded sample of no-fire cell-days from the same region/window.
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    universe = [
        (cell, day) for cell in region_cells(region) for day in days
        if (cell, day) not in positives
    ]
    n_negatives = min(len(universe), round(negatives_per_positive * len(positives)))
    negatives = set(random.Random(seed).sample(universe, n_negatives))

    # Weather: one ERA5 daily series per labeled cell, with the rainfall lead-in.
    labeled = sorted(positives | negatives)
    cells = sorted({cell for cell, _ in labeled})
    centroids = [h3.cell_to_latlng(cell) for cell in cells]
    weather_start = start - timedelta(days=RAINFALL_TRAIL_DAYS)
    series = era5.fetch_daily(centroids, weather_start, end)
    weather: dict[str, dict[date, DailyWeather]] = {
        cell: {dw.day: dw for dw in dws}
        for cell, dws in zip(cells, series, strict=True)
    }

    rows, dropped = _join(labeled, positives, weather)
    manifest = {
        "dataset": "wildfire_cell_day_labels",
        "region": region.key,
        "bbox": vars(region.bbox),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "sources": {
            "labels": "NASA FIRMS area-CSV archive (VIIRS_SNPP_SP)",
            "weather": "ERA5 reanalysis via Open-Meteo /v1/era5 archive API",
        },
        "h3_resolution": 5,
        "detections_fetched": len(detections),
        "positive_cell_days": len(positives),
        "negative_cell_days": len(negatives),
        "negatives_per_positive": negatives_per_positive,
        "rows_dropped_missing_weather": dropped,
        "rows_written": len(rows),
        "rainfall_trail_days": RAINFALL_TRAIL_DAYS,
        "climatology_temp_c": _CLIMATOLOGY_TEMP_C,
        "seed": seed,
        "built_at": datetime.now(UTC).isoformat(),
    }
    logger.info(
        "[INFO] calibration dataset %s %s..%s: %d rows (%d fire / %d no-fire, %d dropped)",
        region.key, start, end, len(rows), len(positives), len(negatives), dropped,
    )
    return CalibrationDataset(rows=rows, manifest=manifest)


def _join(
    labeled: list[tuple[str, date]],
    positives: set[tuple[str, date]],
    weather: dict[str, dict[date, DailyWeather]],
) -> tuple[list[LabeledCellDay], int]:
    """Pair each labeled cell-day with its serve-time features; drop holes, count them."""
    # Regional norm for the rainfall anomaly: mean trailing precipitation over the sample.
    trails: dict[tuple[str, date], float] = {}
    for cell, day in labeled:
        by_day = weather.get(cell, {})
        window = [
            by_day[d].precip_mm
            for i in range(1, RAINFALL_TRAIL_DAYS + 1)
            if (d := day - timedelta(days=i)) in by_day
        ]
        if len(window) >= RAINFALL_TRAIL_DAYS // 2 and day in by_day:
            trails[(cell, day)] = sum(window)
    mean_trail = (sum(trails.values()) / len(trails)) if trails else 0.0

    rows: list[LabeledCellDay] = []
    dropped = 0
    for cell, day in labeled:
        dw = weather.get(cell, {}).get(day)
        trail = trails.get((cell, day))
        if dw is None or trail is None:
            dropped += 1
            continue
        anomaly_pct = ((trail / mean_trail) - 1.0) * 100.0 if mean_trail > 0 else 0.0
        lat, lon = h3.cell_to_latlng(cell)
        rows.append(
            LabeledCellDay(
                cell_id=cell,
                day=day,
                lat=round(lat, 5),
                lon=round(lon, 5),
                temp_anomaly_c=dw.temp_max_c - _CLIMATOLOGY_TEMP_C,
                rainfall_anomaly_pct=anomaly_pct,
                wind_speed_kmh=dw.wind_max_kmh,
                fire=(cell, day) in positives,
            )
        )
    return rows, dropped


def write_dataset(dataset: CalibrationDataset, data_dir: Path) -> Path:
    """Write the labeled table + manifest under ``data/processed/calibration/``.

    Follows the Session-2 staging convention: processed artifacts are re-derivable,
    named by content (region + window), and carry their provenance next to them.
    """
    m = dataset.manifest
    stem = f"wildfire_{m['region']}_{m['window']['start']}_{m['window']['end']}"
    out_dir = data_dir / "processed" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"{stem}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(DATASET_COLUMNS)
        for r in dataset.rows:
            writer.writerow([
                r.cell_id, r.day.isoformat(), r.lat, r.lon,
                f"{r.temp_anomaly_c:.3f}", f"{r.rainfall_anomaly_pct:.3f}",
                f"{r.wind_speed_kmh:.3f}", int(r.fire),
            ])
    (out_dir / f"{stem}.manifest.json").write_text(
        json.dumps(m, indent=2), encoding="utf-8"
    )
    logger.info("[INFO] wrote %d rows to %s", len(dataset.rows), csv_path)
    return csv_path


def read_dataset(csv_path: Path) -> list[LabeledCellDay]:
    """Load a written dataset back — the fitter's and backtester's input."""
    rows: list[LabeledCellDay] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            rows.append(
                LabeledCellDay(
                    cell_id=rec["cell_id"],
                    day=date.fromisoformat(rec["day"]),
                    lat=float(rec["lat"]),
                    lon=float(rec["lon"]),
                    temp_anomaly_c=float(rec["temp_anomaly_c"]),
                    rainfall_anomaly_pct=float(rec["rainfall_anomaly_pct"]),
                    wind_speed_kmh=float(rec["wind_speed_kmh"]),
                    fire=rec["fire"] == "1",
                )
            )
    return rows
