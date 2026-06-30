"""Model-layer tests: training metric thresholds and SHAP explainability.

These guard the predictive quality of VECTIS — if a change regresses the model
below a usable discrimination threshold, CI fails.
"""

from __future__ import annotations

import numpy as np
import pytest

from vectis.data.pipeline.schema import FEATURE_NAMES
from vectis.models.explain import ShapExplainer
from vectis.models.predictor import RiskPredictor
from vectis.models.registry import ModelRegistry
from vectis.models.training import train

pytestmark = pytest.mark.model


def test_training_meets_discrimination_threshold(pipeline_result) -> None:
    outcome = train(pipeline_result, persist=False)
    best = outcome.all_metrics[outcome.best_name]
    # On the seeded sample the signal is strong; require clearly better than chance.
    assert best.roc_auc > 0.75
    assert best.brier < 0.25


def test_all_candidates_trained(pipeline_result) -> None:
    outcome = train(pipeline_result, persist=False)
    assert set(outcome.all_metrics) == {"logistic_regression", "random_forest", "xgboost"}


def test_shap_shape_matches_features(pipeline_result) -> None:
    registry = ModelRegistry()
    pipeline, _ = registry.load("california")
    x = pipeline_result.features[FEATURE_NAMES]
    sv = ShapExplainer(pipeline, x).attribute(x)
    assert sv.shape == (len(x), len(FEATURE_NAMES))
    assert np.isfinite(sv).all()


def test_predictor_produces_explainable_region(pipeline_result) -> None:
    prediction = RiskPredictor("california").predict(pipeline_result)
    assert 0 <= prediction.aggregate_risk_score <= 100
    assert len(prediction.cells) == len(pipeline_result.features)
    assert prediction.top_drivers, "every prediction must have attributed drivers"
    # Each cell carries its own drivers (the 'why').
    assert all(c.drivers for c in prediction.cells)
