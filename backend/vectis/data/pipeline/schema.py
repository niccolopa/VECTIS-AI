"""Canonical feature definitions and dataset schema.

This module is the single source of truth for *what a feature means*. The
sample generator, the pipeline, the ML layer, and the human-readable driver
descriptions in reports all import from here, so they can never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

# Raw columns every connector must provide for the climate-risk vertical.
RAW_COLUMNS: list[str] = [
    "cell_id",
    "lat",
    "lon",
    "temp_anomaly_c",
    "ndvi",
    "drought_index",
    "humidity_pct",
    "wind_speed_kmh",
    "slope_deg",
    "elevation_m",
    "land_cover",
    "historical_fire_count",
]

LABEL = "had_fire"

# Land-cover → flammability of the dominant fuel (0 = non-combustible, 1 = high).
LAND_COVER_FLAMMABILITY: dict[str, float] = {
    "forest": 0.90,
    "shrubland": 0.80,
    "grassland": 0.65,
    "agriculture": 0.40,
    "urban": 0.10,
    "water": 0.00,
}


@dataclass(frozen=True)
class FeatureSpec:
    """Metadata for one engineered model feature.

    ``higher_is_riskier`` documents the *expected* relationship with fire risk
    and is used to sanity-check (not override) the model's learned SHAP signs.
    ``unit`` and ``description`` flow into the human-readable drivers in reports.
    """

    name: str
    label: str
    description: str
    unit: str
    higher_is_riskier: bool


# The engineered feature vector the models consume. Kept small and meaningful so
# SHAP attributions read as plain-language drivers in the Decision Report.
MODEL_FEATURES: list[FeatureSpec] = [
    FeatureSpec("temp_anomaly_c", "Temperature anomaly",
                "Degrees above the seasonal normal temperature.", "°C", True),
    FeatureSpec("vegetation_stress", "Vegetation stress",
                "Dryness/stress of vegetation (1 − NDVI); higher means more flammable fuel.",
                "index", True),
    FeatureSpec("drought_index", "Drought conditions",
                "Standardized dryness of soil and fuel moisture.", "index", True),
    FeatureSpec("humidity_pct", "Relative humidity",
                "Lower humidity dries fuel and raises ignition risk.", "%", False),
    FeatureSpec("wind_speed_kmh", "Wind speed",
                "Wind accelerates fire spread and ember transport.", "km/h", True),
    FeatureSpec("slope_deg", "Terrain slope",
                "Steeper slopes accelerate upslope fire spread.", "degrees", True),
    FeatureSpec("fuel_flammability", "Fuel flammability",
                "Flammability of the dominant land-cover fuel type.", "index", True),
    FeatureSpec("historical_fire_count", "Historical fire activity",
                "Count of recorded fires in the cell's recent history.", "fires", True),
]

FEATURE_NAMES: list[str] = [f.name for f in MODEL_FEATURES]
FEATURE_BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in MODEL_FEATURES}
