"""Hazard-model contract + the one calibration-artifact loading seam, shared per hazard.

Session 34 established the pattern for wildfire: a hazard model ships with **illustrative
coefficients** and every default construction site loads through one seam that picks up a
fitted calibration artifact from disk *when one exists* — so a real calibration deploys as a
pure parameter change, never an architecture change. Session 35 adds flood / earthquake /
cyclone models, which must follow the identical pattern; this module is that pattern
extracted once instead of re-implemented per hazard.

Honesty contract (unchanged from Session 34): **no hazard model in this repository has been
fitted against real ground-truth labels yet.** Every model's defaults are illustrative
priors, marked as such in its module. The artifact directory
(``artifacts/calibration/{hazard}_coefficients.json``) is where a future real calibration
run drops fitted parameters; until then :func:`load_calibrated_or_default` returns the
priors, and a model's existence must never be read as validation.
"""

from __future__ import annotations

import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from vectis.core.config import get_settings
from vectis.core.logging import get_logger

logger = get_logger(__name__)

#: The standing honesty label every driver carries. No hazard model in this repo has been
#: fitted against real labels (see the module docstring), so an attribution is directional
#: — the *sign* and *ranking* are exact from the coefficients in use, the *magnitude* is not
#: a validated effect size.
UNCALIBRATED_DRIVER_CAVEAT = (
    "Illustrative, uncalibrated coefficients — direction and ranking are exact from the "
    "model's own coefficients, the magnitude is not a validated effect size."
)


@dataclass(frozen=True)
class Driver:
    """One factor's exact, signed contribution to a cell's hazard score.

    The closed form the whole session rests on: for a logistic hazard
    ``sigmoid(intercept + Σ coefᵢ·xᵢ)`` a factor's contribution is
    ``coefᵢ × (xᵢ − baselineᵢ)`` in **log-odds** — computed directly from coefficients
    already in use, no SHAP, no new dependency, no approximation. (Earthquake, being
    Omori–Poisson rather than logistic, reports the exact analogous decomposition in
    log-rate; see :meth:`EarthquakeImpactModel.explain`.) This replicates the V1 report's
    driver list honestly, not as validated ground truth — see :data:`UNCALIBRATED_DRIVER_CAVEAT`.
    """

    factor: str
    contribution: float
    input_value: float
    baseline_value: float
    caveat: str = UNCALIBRATED_DRIVER_CAVEAT

    @property
    def direction(self) -> str:
        """``"increases"`` / ``"decreases"`` / ``"neutral"`` — the sign, human-readable."""
        if self.contribution > 0:
            return "increases"
        if self.contribution < 0:
            return "decreases"
        return "neutral"


def _linear_driver(
    factor: str, coef: float, column: np.ndarray | None, baseline_value: float
) -> Driver | None:
    """A logistic factor's exact log-odds contribution, or ``None`` if the input is absent.

    The cell's representative input is the mean over its sampled column (a point estimate
    for a single selected cell); the contribution is ``coef × (mean(x) − baseline)``.
    """
    if column is None or len(column) == 0:
        return None
    x = float(np.mean(np.asarray(column, dtype=float)))
    return Driver(
        factor=factor,
        contribution=coef * (x - baseline_value),
        input_value=x,
        baseline_value=baseline_value,
    )


class HazardModel(ABC):
    """A vectorized map from sampled inputs to per-sample outcome probabilities."""

    @abstractmethod
    def event_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """Return P(hazard event) in ``[0, 1]`` for each sample (array aligned to inputs)."""
        raise NotImplementedError

    def explain(
        self, inputs: Mapping[str, np.ndarray], baseline: Mapping[str, float]
    ) -> list[Driver]:
        """Rank each factor's exact, signed contribution to this cell's hazard score.

        Implemented **once** here for every logistic hazard (wildfire, flood, cyclone):
        each carries a ``coefficients`` dict, so the contribution is
        ``coefᵢ × (mean(inputᵢ) − baselineᵢ)`` in log-odds, ranked by ``|contribution|``.
        Earthquake — Omori–Poisson, no coefficient dict — overrides this with its own
        exact log-rate decomposition. No new dependency; nothing about how risk is computed
        changes — this only exposes an existing computation as a ranked driver list.
        """
        coefficients: Mapping[str, float] | None = getattr(self, "coefficients", None)
        if coefficients is None:  # pragma: no cover - the one non-logistic model overrides
            raise NotImplementedError(
                f"{type(self).__name__} carries no coefficient dict; override explain()."
            )
        drivers = [
            d
            for name, coef in coefficients.items()
            if (d := _linear_driver(name, float(coef), inputs.get(name), baseline.get(name, 0.0)))
            is not None
        ]
        drivers.sort(key=lambda d: abs(d.contribution), reverse=True)
        return drivers


M = TypeVar("M", bound=HazardModel)


def artifact_path_for(hazard: str) -> Path:
    """Where a calibration run deposits fitted parameters for ``hazard``."""
    return get_settings().artifacts_dir / "calibration" / f"{hazard}_coefficients.json"


def load_calibrated_or_default(
    hazard: str,
    model_cls: Callable[..., M],
    artifact_path: Path | None = None,
) -> M:
    """Construct ``hazard``'s model: **calibrated parameters when an artifact exists**,
    the model's illustrative defaults otherwise.

    This is the Session-34 ``default_wildfire_model()`` seam, generalized: an artifact is a
    JSON object whose keys matching ``model_cls``'s constructor parameters are applied
    (scalars coerced to ``float``, mappings to ``{str: float}``); provenance keys are
    ignored. Absent an artifact the model's own defaults apply — unchanged behaviour for a
    fresh clone, and the honest state of this repo for every hazard today.
    """
    path = artifact_path or artifact_path_for(hazard)
    if not path.exists():
        return model_cls()
    artifact = json.loads(path.read_text(encoding="utf-8"))
    params = inspect.signature(model_cls).parameters
    kwargs: dict[str, Any] = {}
    for name, value in artifact.items():
        if name not in params:
            continue  # provenance / bookkeeping keys ride along in the artifact
        kwargs[name] = (
            {k: float(v) for k, v in value.items()} if isinstance(value, Mapping) else float(value)
        )
    logger.info("[INFO] using calibrated %s parameters from %s", hazard, path)
    return model_cls(**kwargs)
