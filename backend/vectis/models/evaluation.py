"""Model evaluation metrics for binary risk classification.

We report threshold metrics (accuracy, precision, recall, F1), discrimination
(ROC-AUC, PR-AUC), and calibration (Brier score), so model selection balances
classification quality, ranking quality, and the calibrated probabilities the
risk score depends on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass(frozen=True)
class Metrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier: float
    n: int
    positive_rate: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    @property
    def selection_score(self) -> float:
        """Composite score for model selection.

        Rewards discrimination (ROC-AUC) while penalizing poor calibration
        (Brier). Calibration matters because the risk score is a probability.
        """
        return self.roc_auc - 0.5 * self.brier


def evaluate(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> Metrics:
    """Compute evaluation metrics from ground truth and predicted probabilities."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    y_pred = (y_prob >= threshold).astype(int)

    # ROC/PR-AUC are undefined with a single class present; degrade gracefully.
    single_class = len(np.unique(y_true)) < 2
    return Metrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision=float(precision_score(y_true, y_pred, zero_division=0)),
        recall=float(recall_score(y_true, y_pred, zero_division=0)),
        f1=float(f1_score(y_true, y_pred, zero_division=0)),
        roc_auc=float("nan") if single_class else float(roc_auc_score(y_true, y_prob)),
        pr_auc=float("nan") if single_class else float(average_precision_score(y_true, y_prob)),
        brier=float(brier_score_loss(y_true, y_prob)),
        n=int(len(y_true)),
        positive_rate=float(y_true.mean()),
    )
