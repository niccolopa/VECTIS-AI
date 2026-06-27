"""Probability — Bayesian updating and reduction of MC samples to distributions."""

from vectis.simulation.probability.bayesian import (
    BayesianUpdater,
    GaussianBayesianUpdater,
    Observation,
)
from vectis.simulation.probability.calibration import (
    CalibrationRecord,
    Calibrator,
    brier_score,
)
from vectis.simulation.probability.uncertainty import (
    confidence_from_entropy,
    confidence_from_variance,
    distribution_confidence,
    posterior_mixture_risk,
    scenario_confidence,
    shannon_entropy,
)

__all__ = [
    "BayesianUpdater",
    "GaussianBayesianUpdater",
    "Observation",
    "CalibrationRecord",
    "Calibrator",
    "brier_score",
    "confidence_from_entropy",
    "confidence_from_variance",
    "distribution_confidence",
    "posterior_mixture_risk",
    "scenario_confidence",
    "shannon_entropy",
]
