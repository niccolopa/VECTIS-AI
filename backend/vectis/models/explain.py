"""SHAP-based explainability.

Turns a fitted scaler+estimator pipeline into per-cell, per-feature SHAP
attributions, normalized to the positive ("fire") class in log-odds space.
These attributions become the human-readable drivers in the Decision Report —
this is how VECTIS answers "why did the model decide this?".
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap

from vectis.core.logging import get_logger
from vectis.data.pipeline.schema import FEATURE_NAMES

log = get_logger(__name__)


def _positive_class(values: np.ndarray | list) -> np.ndarray:
    """Normalize SHAP output across estimator/version differences.

    Returns a 2D array (n_samples, n_features) of contributions toward the
    positive class.
    """
    if isinstance(values, list):  # e.g. [class0, class1] from some TreeExplainers
        values = values[-1]
    arr = np.asarray(values)
    if arr.ndim == 3:  # (n_samples, n_features, n_classes)
        arr = arr[:, :, -1]
    return arr


class ShapExplainer:
    """Wraps a fitted pipeline to produce SHAP attributions on raw features."""

    def __init__(self, pipeline: Any, background: pd.DataFrame) -> None:
        self.scaler = pipeline.named_steps["scaler"]
        self.model = pipeline.named_steps["model"]
        bg = self.scaler.transform(background[FEATURE_NAMES])
        try:
            # TreeExplainer covers RandomForest and XGBoost; LinearExplainer the
            # logistic baseline. shap.Explainer auto-dispatches as a fallback.
            self.explainer = shap.Explainer(self.model, bg)
        except Exception:  # pragma: no cover - defensive across shap versions
            self.explainer = shap.KernelExplainer(self.model.predict_proba, bg)

    def attribute(self, x: pd.DataFrame) -> np.ndarray:
        """Return SHAP values for ``x`` as (n_samples, n_features)."""
        xs = self.scaler.transform(x[FEATURE_NAMES])
        explanation = self.explainer(xs)
        values = explanation.values if hasattr(explanation, "values") else explanation
        sv = _positive_class(values)
        if sv.shape[1] != len(FEATURE_NAMES):  # pragma: no cover
            raise ValueError(f"Unexpected SHAP shape {sv.shape} for {len(FEATURE_NAMES)} features")
        return sv
