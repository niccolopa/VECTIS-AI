"""Kalman filter foundation — predict/correct state estimation with uncertainty.

Session 20 replaces the Session-19 exponential-moving-average merge with a proper
**1D Kalman filter**: each variable is a Gaussian belief ``(mean, variance)`` that is
**predicted** forward in time (uncertainty grows) and then **corrected** by each new
observation, weighted against the observation's own uncertainty via the Kalman gain.

The headline property: as consistent observations arrive the variance *drops* — the
system becomes measurably more confident — which a fixed-weight EMA can never do.

Pure ``float`` arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

from vectis.realtime.forecasting.kalman.filter import (
    Gaussian,
    confidence_to_variance,
    correct,
    kalman_gain,
    predict,
)
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState, VariableEstimate

__all__ = [
    "Gaussian",
    "KalmanCellState",
    "VariableEstimate",
    "confidence_to_variance",
    "correct",
    "kalman_gain",
    "predict",
]
