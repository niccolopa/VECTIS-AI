"""Risk prediction with built-in explainability.

``RiskPredictor`` loads the deployed model for a region and produces, for each
grid cell, a calibrated probability, a 0–100 risk score, and the top SHAP
drivers. It also aggregates a region-level prediction with the dominant drivers
across the area.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vectis.core.schemas import CellPrediction, Driver, RegionPrediction
from vectis.data.pipeline.runner import PipelineResult
from vectis.data.pipeline.schema import FEATURE_BY_NAME, FEATURE_NAMES
from vectis.models.explain import ShapExplainer
from vectis.models.registry import ModelCard, ModelRegistry


def _driver(feature: str, value: float, shap_value: float) -> Driver:
    spec = FEATURE_BY_NAME[feature]
    return Driver.from_shap(
        feature=feature, value=float(value), shap_value=float(shap_value),
        label=spec.label, description=spec.description,
    )


class RiskPredictor:
    """Loads a trained model and produces explainable predictions for a region."""

    def __init__(self, region: str, registry: ModelRegistry | None = None) -> None:
        self.region = region
        self.registry = registry or ModelRegistry()
        self.pipeline, self.card = self.registry.load(region)

    @property
    def model_card(self) -> ModelCard:
        return self.card

    def predict(self, result: PipelineResult, *, top_k: int = 4) -> RegionPrediction:
        """Predict cell-level risk + drivers and aggregate to the region."""
        df = result.features.reset_index(drop=True)
        x = df[FEATURE_NAMES]

        proba = self.pipeline.predict_proba(x)[:, 1]
        shap_values = ShapExplainer(self.pipeline, x).attribute(x)

        cells: list[CellPrediction] = []
        for i, row in df.iterrows():
            sv = shap_values[i]
            order = np.argsort(np.abs(sv))[::-1][:top_k]
            drivers = [_driver(FEATURE_NAMES[j], row[FEATURE_NAMES[j]], sv[j]) for j in order]
            cells.append(
                CellPrediction(
                    cell_id=str(row["cell_id"]),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    probability=float(proba[i]),
                    risk_score=round(float(proba[i]) * 100, 1),
                    drivers=drivers,
                )
            )

        # Region aggregate: blend the mean with the 90th percentile so hotspots
        # are not averaged away — a region with a few severe cells is risky.
        mean_p = float(np.mean(proba))
        p90 = float(np.percentile(proba, 90))
        aggregate = round((0.4 * mean_p + 0.6 * p90) * 100, 1)

        top_drivers = self._region_drivers(df, shap_values, top_k=max(top_k, 5))

        return RegionPrediction(
            region=self.region,
            model_name=self.card.model_name,
            model_card_ref=self.card.ref,
            cells=cells,
            mean_probability=round(mean_p, 4),
            aggregate_risk_score=aggregate,
            top_drivers=top_drivers,
        )

    def _region_drivers(self, df: pd.DataFrame, shap_values: np.ndarray,
                        top_k: int) -> list[Driver]:
        """Rank drivers across the whole region by mean |SHAP|."""
        mean_abs = np.abs(shap_values).mean(axis=0)
        mean_signed = shap_values.mean(axis=0)
        order = np.argsort(mean_abs)[::-1][:top_k]
        drivers: list[Driver] = []
        for j in order:
            feature = FEATURE_NAMES[j]
            drivers.append(_driver(feature, float(df[feature].mean()), float(mean_signed[j])))
        return drivers
