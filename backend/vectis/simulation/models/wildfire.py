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

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.special import expit  # numerically-stable, C-level logistic sigmoid

from vectis.core.config import get_settings
from vectis.core.logging import get_logger

logger = get_logger(__name__)


class HazardModel(ABC):
    """A vectorized map from sampled inputs to per-sample outcome probabilities."""

    @abstractmethod
    def fire_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """Return P(fire) in ``[0, 1]`` for each sample (array aligned to inputs)."""
        raise NotImplementedError


# Illustrative log-odds coefficients: hotter, drier, windier, more ignition → higher risk.
# These remain the fallback when no calibration artifact exists. The Session-34 fitting
# pipeline (vectis.calibration.fit) replaces them with FIRMS/ERA5-fitted values via the
# artifact default_wildfire_model() loads; the Session-34 environment had no FIRMS
# MAP_KEY, so no real fit ran and these are still the priors.
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


def default_wildfire_model(artifact_path: Path | None = None) -> WildfireHazardModel:
    """The model consumers should default to: **calibrated coefficients when they exist**.

    Session 34's fitting pipeline writes ``artifacts/calibration/wildfire_coefficients.json``;
    when that artifact is present, every default construction site (the Monte Carlo engine,
    the screening index) picks up the fitted coefficients through this one seam. Absent an
    artifact, the illustrative priors above apply — unchanged behaviour for a fresh clone.
    """
    path = artifact_path or (
        get_settings().artifacts_dir / "calibration" / "wildfire_coefficients.json"
    )
    if not path.exists():
        return WildfireHazardModel()
    artifact = json.loads(path.read_text(encoding="utf-8"))
    logger.info("[INFO] using calibrated wildfire coefficients from %s", path)
    return WildfireHazardModel(
        intercept=float(artifact["intercept"]),
        coefficients={k: float(v) for k, v in artifact["coefficients"].items()},
    )
