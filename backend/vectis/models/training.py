"""Training pipeline: fit baseline models, evaluate, select the best, persist.

Baselines: Logistic Regression (calibrated linear baseline), Random Forest, and
XGBoost. Each is wrapped in a ``StandardScaler`` pipeline so the linear model is
well-conditioned and SHAP operates on a consistent feature space. Selection uses
a composite of discrimination and calibration (see ``evaluation.Metrics``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.data.pipeline.runner import PipelineResult
from vectis.data.pipeline.schema import FEATURE_NAMES, LABEL
from vectis.models.evaluation import Metrics, evaluate
from vectis.models.registry import ModelCard, ModelRegistry

log = get_logger(__name__)


def _candidates(seed: int) -> dict[str, Any]:
    """The baseline model zoo, each as a scaler+estimator pipeline."""
    return {
        "logistic_regression": Pipeline(
            [("scaler", StandardScaler()),
             ("model", LogisticRegression(max_iter=1000, random_state=seed))]
        ),
        "random_forest": Pipeline(
            [("scaler", StandardScaler()),
             ("model", RandomForestClassifier(
                 n_estimators=300, max_depth=8, min_samples_leaf=3,
                 random_state=seed, n_jobs=-1))]
        ),
        "xgboost": Pipeline(
            [("scaler", StandardScaler()),
             ("model", XGBClassifier(
                 n_estimators=300, max_depth=4, learning_rate=0.05,
                 subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                 random_state=seed, n_jobs=-1))]
        ),
    }


@dataclass
class TrainingOutcome:
    best_name: str
    pipeline: Any
    card: ModelCard
    all_metrics: dict[str, Metrics]


def train(result: PipelineResult, *, registry: ModelRegistry | None = None,
          persist: bool = True) -> TrainingOutcome:
    """Train baselines on a pipeline result and persist the best model."""
    if not result.has_label:
        raise ValueError("Training requires labeled data (missing 'had_fire').")

    settings = get_settings()
    seed = settings.random_seed
    registry = registry or ModelRegistry()

    df = result.features
    x = df[FEATURE_NAMES]
    y = df[LABEL].astype(int)

    stratify = y if y.nunique() > 1 else None
    x_tr, x_te, y_tr, y_te = train_test_split(
        x, y, test_size=0.25, random_state=seed, stratify=stratify
    )

    all_metrics: dict[str, Metrics] = {}
    for name, pipe in _candidates(seed).items():
        pipe.fit(x_tr, y_tr)
        prob = pipe.predict_proba(x_te)[:, 1]
        metrics = evaluate(y_te.to_numpy(), prob)
        all_metrics[name] = metrics
        log.info("train.candidate", model=name, **{k: round(v, 4) if isinstance(v, float) else v
                                                    for k, v in metrics.as_dict().items()})

    best_name = max(all_metrics, key=lambda n: all_metrics[n].selection_score)

    # Refit the winner on all data for the deployed artifact.
    best_pipeline = _candidates(seed)[best_name]
    best_pipeline.fit(x, y)

    card = ModelCard(
        model_name=best_name,
        region=result.region_key,
        dataset_version=result.dataset_version,
        feature_names=FEATURE_NAMES,
        metrics=_round(all_metrics[best_name].as_dict()),
        candidates={n: _round(m.as_dict()) for n, m in all_metrics.items()},
        seed=seed,
        notes="Selected by composite ROC-AUC minus 0.5*Brier (discrimination + calibration).",
    )
    if persist:
        path = registry.save(result.region_key, best_pipeline, card)
        log.info("train.saved", model=best_name, ref=card.ref, path=str(path))

    return TrainingOutcome(best_name, best_pipeline, card, all_metrics)


def _round(d: dict[str, float]) -> dict[str, float]:
    return {k: (round(v, 6) if isinstance(v, float) and np.isfinite(v) else v)
            for k, v in d.items()}
