"""Calibration — is the engine's confidence *earned*? (blueprint)

A model can be sharp and wrong: chronically forecasting 90% on events that happen
60% of the time. Calibration measures the gap between **predicted probabilities**
and **observed frequencies**, so the Confidence Score from ``uncertainty.py`` can
be audited against reality rather than trusted blindly.

Session-8 scope is a **blueprint**: the data structure plus the headline metric
(:func:`brier_score`) are implemented and tested, because they are one-liners and
give a runnable check. Reliability-diagram binning and recalibration fitting
(isotonic / Platt scaling) are stubbed with clear contracts — they need a real
backlog of (prediction, outcome) pairs, which only exists once live FIRMS labels
land (see HANDOFF Next Steps).

Pure ``numpy`` — no LLM in the scoring loop.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    """Accumulates forecast/outcome pairs and reports calibration. (blueprint)

    Wire each resolved forecast in with :meth:`record`, then read :meth:`summary`.
    Only :func:`brier_score` is wired today; the reliability curve and a fitted
    recalibration map are deferred until a real outcome backlog exists.
    """

    records: list[CalibrationRecord] = field(default_factory=list)

    def record(self, predicted: float, occurred: bool) -> None:
        """Log one resolved forecast."""
        self.records.append(CalibrationRecord(predicted=predicted, occurred=occurred))

    def brier(self) -> float:
        """Current Brier score over all logged records."""
        return brier_score(self.records)

    def reliability_curve(self, n_bins: int = 10) -> list[tuple[float, float, int]]:
        """(blueprint) Per-bin (mean predicted, observed frequency, count).

        Bins predictions into ``n_bins`` equal-width buckets over ``[0, 1]``; a
        well-calibrated model lies on the diagonal (predicted ≈ observed). Deferred
        until there are enough records for the bins to be meaningful.
        """
        raise NotImplementedError("reliability_curve is a blueprint — needs a FIRMS-label backlog.")

    def fit_recalibration(self) -> object:
        """(blueprint) Fit a monotone recalibration map (isotonic / Platt scaling).

        Returns a callable ``p_raw -> p_calibrated`` that corrects systematic
        over/under-confidence. Deferred — fitting needs the same outcome backlog.
        """
        raise NotImplementedError("fit_recalibration is a blueprint — needs a FIRMS-label backlog.")


if __name__ == "__main__":
    # ponytail: self-check the one implemented metric.
    perfect = [CalibrationRecord(1.0, True), CalibrationRecord(0.0, False)]
    assert brier_score(perfect) == 0.0
    coin = [CalibrationRecord(0.5, True), CalibrationRecord(0.5, False)]
    assert abs(brier_score(coin) - 0.25) < 1e-12
    assert brier_score([]) == 0.0
    print("simulation.probability.calibration self-check OK")
