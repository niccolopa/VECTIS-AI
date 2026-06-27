"""Reproducible, vectorized sampling of a ``WorldState`` into input arrays.

All randomness flows from an explicit ``numpy`` ``Generator``/``SeedSequence``
derived from the run's integer seed, so the same seed yields identical draws on
any machine. For chunked/parallel execution we use ``SeedSequence.spawn`` to
derive *statistically independent* child streams per worker — the canonical
numpy pattern that keeps parallel runs reproducible and free of cross-stream
correlation.

The output of :func:`sample_state` is a ``{variable_name: ndarray}`` mapping —
columns of length ``size`` — which the (vectorized) hazard model consumes
directly. No Python loop touches an individual sample.
"""

from __future__ import annotations

import numpy as np

from vectis.simulation.engine.distributions import distribution_for
from vectis.simulation.schemas import Scenario, StateVariable, WorldState


def split_iterations(total: int, parts: int) -> list[int]:
    """Split ``total`` iterations into ``parts`` balanced chunk sizes (sum == total)."""
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def _perturb(var: StateVariable, delta: float) -> StateVariable:
    """Return ``var`` shifted by a scenario's additive perturbation (or itself if 0).

    The shift moves the variable's central location (``value``) and, for bounded
    families, its ``low``/``high`` together, so a UNIFORM band slides rather than
    widens.
    """
    if delta == 0.0:
        return var
    update: dict[str, float] = {"value": var.value + delta}
    if var.low is not None:
        update["low"] = var.low + delta
    if var.high is not None:
        update["high"] = var.high + delta
    return var.model_copy(update=update)


def sample_state(
    state: WorldState, scenario: Scenario, rng: np.random.Generator, size: int
) -> dict[str, np.ndarray]:
    """Draw ``size`` samples of each state variable under ``scenario``.

    Each variable is perturbed by the scenario, mapped to its distribution, and
    sampled as a length-``size`` vector. Returns a name→array mapping.
    """
    out: dict[str, np.ndarray] = {}
    for var in state.variables:
        delta = scenario.perturbations.get(var.name, 0.0)
        out[var.name] = distribution_for(_perturb(var, delta)).sample(rng, size)
    return out
