"""Generate the deterministic Liguria sample dataset.

This produces a synthetic-but-physically-plausible grid of wildfire-risk
observations over Liguria. It is *not* real satellite data — it is a
reproducible stand-in so VECTIS runs end-to-end offline. The label
(``had_fire``) is generated as a noisy function of the features, so the ML
layer learns a real, explainable signal and SHAP recovers meaningful drivers.

Run: ``python -m vectis.scripts.generate_sample`` (or ``make seed``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.data.regions import LIGURIA, Region

log = get_logger(__name__)

_LAND_COVERS = ["forest", "shrubland", "grassland", "agriculture", "urban", "water"]
# Probability weights: Liguria is largely forested/hilly.
_LAND_COVER_P = [0.34, 0.24, 0.12, 0.14, 0.13, 0.03]
_FLAMMABILITY = {
    "forest": 0.90, "shrubland": 0.80, "grassland": 0.65,
    "agriculture": 0.40, "urban": 0.10, "water": 0.00,
}


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def build_frame(region: Region, seed: int) -> pd.DataFrame:
    """Build the raw observation frame for a region's grid."""
    rng = np.random.default_rng(seed)
    n = region.n_cells
    bb = region.bbox

    # Regular grid of cell centers.
    lats = np.linspace(bb.min_lat, bb.max_lat, region.rows)
    lons = np.linspace(bb.min_lon, bb.max_lon, region.cols)
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")
    lat = grid_lat.ravel()
    lon = grid_lon.ravel()

    # Elevation rises inland (north); coast is to the south.
    coast_proximity = (lat - bb.min_lat) / (bb.max_lat - bb.min_lat)  # 0 coast → 1 inland
    elevation = np.clip(coast_proximity * 1400 + rng.normal(0, 120, n), 0, 1800)

    # A smooth "hot & dry summer" field, hotter inland, plus local noise.
    temp_anomaly = np.clip(2.5 + 3.0 * coast_proximity + rng.normal(0, 1.2, n), -5, 12)
    drought = np.clip(0.45 + 0.35 * coast_proximity + rng.normal(0, 0.12, n), 0, 1)
    humidity = np.clip(70 - 30 * coast_proximity + rng.normal(0, 8, n), 10, 100)
    wind = np.clip(rng.gamma(2.0, 6.0, n), 0, 90)
    slope = np.clip(coast_proximity * 25 + rng.normal(0, 6, n), 0, 60)
    ndvi = np.clip(0.65 - 0.25 * drought + rng.normal(0, 0.08, n), -0.1, 0.95)

    land_cover = rng.choice(_LAND_COVERS, size=n, p=_LAND_COVER_P)
    flammability = np.array([_FLAMMABILITY[c] for c in land_cover])

    historical = rng.poisson(np.clip(flammability * 3 * drought, 0, None)).astype(int)

    # Latent fire-risk: standardized drivers with physically sensible signs.
    veg_stress = np.clip(1 - ndvi, 0, 1)
    latent = (
        0.9 * (temp_anomaly - 4) / 3
        + 1.1 * (drought - 0.5) / 0.2
        + 1.0 * (veg_stress - 0.4) / 0.2
        - 0.8 * (humidity - 45) / 20
        + 0.5 * (wind - 12) / 10
        + 0.4 * (slope - 12) / 10
        + 1.2 * (flammability - 0.6) / 0.3
        + 0.6 * (historical - 1)
        - 1.4
    )
    prob = _sigmoid(latent + rng.normal(0, 0.4, n))
    had_fire = (rng.random(n) < prob).astype(int)

    return pd.DataFrame(
        {
            "cell_id": [f"{region.key}-{i:03d}" for i in range(n)],
            "lat": np.round(lat, 5),
            "lon": np.round(lon, 5),
            "temp_anomaly_c": np.round(temp_anomaly, 2),
            "ndvi": np.round(ndvi, 3),
            "drought_index": np.round(drought, 3),
            "humidity_pct": np.round(humidity, 1),
            "wind_speed_kmh": np.round(wind, 1),
            "slope_deg": np.round(slope, 1),
            "elevation_m": np.round(elevation, 0).astype(int),
            "land_cover": land_cover,
            "historical_fire_count": historical,
            "had_fire": had_fire,
        }
    )


def generate(region: Region = LIGURIA, seed: int | None = None) -> str:
    """Generate and persist the sample dataset; returns the output path."""
    settings = get_settings()
    seed = settings.random_seed if seed is None else seed
    frame = build_frame(region, seed)

    out_dir = settings.sample_dir / region.key
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cells.csv"
    frame.to_csv(out_path, index=False)

    log.info(
        "sample.generated",
        region=region.key,
        cells=len(frame),
        fire_rate=round(float(frame["had_fire"].mean()), 3),
        path=str(out_path),
    )
    return str(out_path)


def main() -> None:
    path = generate()
    print(f"Sample dataset written to {path}")


if __name__ == "__main__":
    main()
