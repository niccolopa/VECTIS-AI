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
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from vectis.core.config import get_settings
from vectis.core.logging import get_logger

logger = get_logger(__name__)


class HazardModel(ABC):
    """A vectorized map from sampled inputs to per-sample outcome probabilities."""

    @abstractmethod
    def event_probability(self, inputs: Mapping[str, np.ndarray]) -> np.ndarray:
        """Return P(hazard event) in ``[0, 1]`` for each sample (array aligned to inputs)."""
        raise NotImplementedError


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
