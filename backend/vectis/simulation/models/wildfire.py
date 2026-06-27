"""Wildfire ignition hazard — the stochastic-model layer for the use case.

Maps a set of sampled environmental inputs to a per-sample fire probability via a
**vectorized logistic** function::

    P(fire) = sigmoid(intercept + Σ coefᵢ · inputᵢ)

The stochasticity of the forecast comes from sampling the *inputs* (uncertainty
propagation); given inputs, the hazard is a deterministic, C-level numpy/scipy
computation — never an LLM. Coefficients are illustrative and meant to be
calibrated against real labels (NASA FIRMS) later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
from scipy.special import expit  # numerically-stable, C-level logistic sigmoid


class HazardModel(ABC):
    """A vectorized map from sampled inputs to per-sample outcome probabilities."""

    @abstractmethod
    def fire_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """Return P(fire) in ``[0, 1]`` for each sample (array aligned to inputs)."""
        raise NotImplementedError


# Illustrative log-odds coefficients: hotter, drier, windier, more ignition → higher risk.
# ponytail: hand-tuned priors — calibrate against FIRMS labels when live data lands.
_DEFAULT_COEFFICIENTS: dict[str, float] = {
    "temp_anomaly_c": 0.55,
    "rainfall_anomaly_pct": -0.03,
    "wind_speed_kmh": 0.02,
    "ignition_sources": 0.35,
}


@dataclass(frozen=True)
class WildfireHazardModel(HazardModel):
    """Logistic wildfire-ignition hazard over environmental drivers."""

    intercept: float = -1.5
    coefficients: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_COEFFICIENTS)
    )

    def fire_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        if not inputs:
            return np.empty(0, dtype=float)
        size = len(next(iter(inputs.values())))
        # Accumulate the log-odds vector; every op below is whole-array (vectorized).
        z = np.full(size, self.intercept, dtype=float)
        for name, coef in self.coefficients.items():
            column = inputs.get(name)
            if column is not None:
                z = z + coef * column
        return np.asarray(expit(z), dtype=float)
