"""Tests for the classification evaluation metrics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from vectis.models.evaluation import evaluate

pytestmark = pytest.mark.model


def test_perfect_predictions_score_one() -> None:
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.01, 0.2, 0.8, 0.99])
    m = evaluate(y_true, y_prob)
    assert m.accuracy == 1.0
    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.f1 == 1.0
    assert m.roc_auc == 1.0


def test_all_metrics_present_and_bounded() -> None:
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=50)
    y_prob = rng.random(50)
    d = evaluate(y_true, y_prob).as_dict()
    for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "brier"):
        assert key in d
    for key in ("accuracy", "precision", "recall", "f1"):
        assert 0.0 <= d[key] <= 1.0


def test_single_class_degrades_gracefully() -> None:
    # ROC/PR-AUC are undefined with one class; metrics should be NaN, not raise.
    m = evaluate(np.array([1, 1, 1]), np.array([0.6, 0.7, 0.8]))
    assert math.isnan(m.roc_auc)
    assert m.recall == 1.0  # all positives predicted positive at threshold 0.5
