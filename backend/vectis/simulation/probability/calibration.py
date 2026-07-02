"""Calibration — is the engine's confidence *earned*?

A model can be sharp and wrong: chronically forecasting 90% on events that happen
60% of the time. Calibration measures the gap between **predicted probabilities**
and **observed frequencies**, so the Confidence Score from ``uncertainty.py`` can
be audited against reality rather than trusted blindly.

Session 8 shipped the data structure and :func:`brier_score`; Session 34 completed
the reliability-diagram binning and recalibration fitting (isotonic / Platt), which
the calibration backtest (:mod:`vectis.calibration.backtest`) exercises against a
resolved-forecast backlog. The metrics are backlog-agnostic: they score whatever
(prediction, outcome) pairs are recorded, whether fixture-based or real FIRMS labels.

``numpy`` + ``scikit-learn`` fitting — no LLM in the scoring loop.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class CalibrationRecord:
    """One forecast paired with what actually happened.

    ``predicted`` is the probability the model assigned in ``[0, 1]``; ``occurred``
    is whether the event then happened. The atom of every calibration metric.
    """

    predicted: float
    occurred: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.predicted <= 1.0:
            raise ValueError(f"predicted must be a probability in [0, 1], got {self.predicted}")


def brier_score(records: Sequence[CalibrationRecord]) -> float:
    """Mean squared error between predicted probabilities and outcomes.

    ``BS = mean((predicted - occurred)²)`` over all records, in ``[0, 1]`` — lower
    is better (0 = perfect, 0.25 = the score of an always-50% forecaster). The
    standard scalar summary of probabilistic accuracy; an empty backlog scores 0.
    """
    if not records:
        return 0.0
    predicted = np.array([r.predicted for r in records], dtype=float)
    occurred = np.array([r.occurred for r in records], dtype=float)
    return float(np.mean((predicted - occurred) ** 2))


@dataclass
class Calibrator:
    """Accumulates forecast/outcome pairs and reports calibration.

    Wire each resolved forecast in with :meth:`record`, then read :meth:`brier`,
    :meth:`reliability_curve`, or fit a corrective map with :meth:`fit_recalibration`.
    """

    records: list[CalibrationRecord] = field(default_factory=list)

    def record(self, predicted: float, occurred: bool) -> None:
        """Log one resolved forecast."""
        self.records.append(CalibrationRecord(predicted=predicted, occurred=occurred))

    def brier(self) -> float:
        """Current Brier score over all logged records."""
        return brier_score(self.records)

    def reliability_curve(self, n_bins: int = 10) -> list[tuple[float, float, int]]:
        """Per-bin (mean predicted, observed frequency, count) — the reliability diagram.

        Bins predictions into ``n_bins`` equal-width buckets over ``[0, 1]``; a
        well-calibrated model lies on the diagonal (predicted ≈ observed). Empty
        bins are omitted rather than reported as zeros.
        """
        if n_bins < 1:
            raise ValueError("n_bins must be at least 1")
        predicted = np.array([r.predicted for r in self.records], dtype=float)
        occurred = np.array([r.occurred for r in self.records], dtype=float)
        bin_index = np.minimum((predicted * n_bins).astype(int), n_bins - 1)
        return [
            (float(predicted[mask].mean()), float(occurred[mask].mean()), int(mask.sum()))
            for b in range(n_bins)
            if (mask := bin_index == b).any()
        ]

    def fit_recalibration(self, method: str = "isotonic") -> Callable[[float], float]:
        """Fit a monotone recalibration map (``isotonic`` or ``platt`` scaling).

        Returns a callable ``p_raw -> p_calibrated`` that corrects systematic
        over/under-confidence, fit on the recorded backlog. Both methods need
        records of both outcomes — a one-sided backlog cannot identify a map.
        """
        occurred = [r.occurred for r in self.records]
        if not (any(occurred) and not all(occurred)):
            raise ValueError("recalibration needs records of both outcomes")
        predicted = np.array([r.predicted for r in self.records], dtype=float)
        outcomes = np.array(occurred, dtype=float)

        if method == "isotonic":
            from sklearn.isotonic import IsotonicRegression

            iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
            iso.fit(predicted, outcomes)
            return lambda p: float(iso.predict(np.atleast_1d(p))[0])
        if method == "platt":
            from sklearn.linear_model import LogisticRegression

            platt = LogisticRegression()
            platt.fit(predicted.reshape(-1, 1), outcomes.astype(int))
            return lambda p: float(platt.predict_proba(np.atleast_1d(p).reshape(-1, 1))[0, 1])
        raise ValueError(f"unknown recalibration method {method!r} (isotonic|platt)")


if __name__ == "__main__":
    # ponytail: self-check the one implemented metric.
    perfect = [CalibrationRecord(1.0, True), CalibrationRecord(0.0, False)]
    assert brier_score(perfect) == 0.0
    coin = [CalibrationRecord(0.5, True), CalibrationRecord(0.5, False)]
    assert abs(brier_score(coin) - 0.25) < 1e-12
    assert brier_score([]) == 0.0
    print("simulation.probability.calibration self-check OK")
