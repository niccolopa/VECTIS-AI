"""Individual pipeline stages: validate → clean → feature-engineer.

Each stage is a pure function ``DataFrame -> DataFrame`` (plus the validation
gate), which keeps them independently testable and easy to reason about.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vectis.core.exceptions import DataValidationError
from vectis.data.pipeline.schema import (
    FEATURE_NAMES,
    LABEL,
    LAND_COVER_FLAMMABILITY,
    RAW_COLUMNS,
)

# Plausible physical ranges used by validation to catch corrupt inputs early.
_RANGES: dict[str, tuple[float, float]] = {
    "lat": (-90, 90),
    "lon": (-180, 180),
    "temp_anomaly_c": (-20, 25),
    "ndvi": (-0.2, 1.0),
    "drought_index": (0, 1),
    "humidity_pct": (0, 100),
    "wind_speed_kmh": (0, 200),
    "slope_deg": (0, 90),
    "elevation_m": (-50, 5000),
    "historical_fire_count": (0, 1000),
}


def validate(df: pd.DataFrame, *, require_label: bool = False) -> pd.DataFrame:
    """Assert the raw frame has the expected columns and in-range values.

    Raises :class:`DataValidationError` on the first structural problem.
    """
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if require_label and LABEL not in df.columns:
        raise DataValidationError(f"Missing label column '{LABEL}'")
    if df.empty:
        raise DataValidationError("Raw frame is empty")

    for col, (lo, hi) in _RANGES.items():
        series = df[col].dropna()
        if not series.between(lo, hi).all():
            bad = series[~series.between(lo, hi)].head(3).tolist()
            raise DataValidationError(f"Column '{col}' has out-of-range values: {bad}")

    unknown = set(df["land_cover"].unique()) - set(LAND_COVER_FLAMMABILITY)
    if unknown:
        raise DataValidationError(f"Unknown land_cover categories: {sorted(unknown)}")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Impute missing numerics with column medians and de-duplicate cells."""
    df = df.drop_duplicates(subset="cell_id").copy()
    numeric = df.select_dtypes(include="number").columns
    df[numeric] = df[numeric].fillna(df[numeric].median(numeric_only=True))
    df["land_cover"] = df["land_cover"].fillna("shrubland")
    return df.reset_index(drop=True)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive the model feature vector from cleaned raw columns.

    Adds the engineered columns in ``FEATURE_NAMES`` while preserving identity
    (``cell_id``/``lat``/``lon``) and the label when present.
    """
    out = df.copy()
    # Vegetation stress: inverse of greenness, clipped to [0, 1].
    out["vegetation_stress"] = (1.0 - out["ndvi"]).clip(0.0, 1.0)
    # Map land cover to fuel flammability.
    out["fuel_flammability"] = out["land_cover"].map(LAND_COVER_FLAMMABILITY).astype(float)

    keep = ["cell_id", "lat", "lon", *FEATURE_NAMES]
    if LABEL in out.columns:
        keep.append(LABEL)
    result = out[keep]

    if result[FEATURE_NAMES].isna().any().any():
        raise DataValidationError("Engineered features contain NaNs after cleaning")
    # Guard against non-finite values reaching the model.
    if not np.isfinite(result[FEATURE_NAMES].to_numpy()).all():
        raise DataValidationError("Engineered features contain non-finite values")
    return result.reset_index(drop=True)
