"""Confidence scoring — how *sure* is the engine about its own forecast?

A posterior that concentrates on one future is more trustworthy than one spread
thinly across every branch; a tight outcome distribution is more trustworthy than
a fat one. This module turns that intuition into a ``[0, 1]`` **Confidence Score**
that is *inversely* related to the spread of a probability distribution:

- **Categorical** (a :class:`~vectis.simulation.schemas.ScenarioSet`): confidence
  is ``1 - normalized Shannon entropy``. A uniform posterior (maximum entropy)
  scores 0; all mass on one scenario (zero entropy) scores 1.
- **Continuous** (a :class:`~vectis.simulation.schemas.ProbabilityDistribution`):
  confidence falls off with the standard deviation relative to a reference scale.

Pure ``numpy`` — no LLM, no model. These are deterministic functions of numbers
the engine already produced.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from vectis.simulation.schemas import ProbabilityDistribution, ScenarioSet

# Below this total probability mass a weight set is treated as un-normalized/empty.
_MASS_FLOOR = 1e-12


def shannon_entropy(probs: Sequence[float]) -> float:
    """Shannon entropy ``H = -Σ pᵢ ln pᵢ`` (nats) of a probability vector.

    Zero-probability terms contribute 0 (the ``0·ln 0 → 0`` convention). Input is
    normalized defensively so callers may pass un-normalized weights.
    """
    p = np.asarray(probs, dtype=float)
    total = p.sum()
    if total < _MASS_FLOOR:
        return 0.0
    p = p[p > 0.0] / total
    return float(-np.sum(p * np.log(p)))


def normalized_entropy(probs: Sequence[float]) -> float:
    """Entropy scaled to ``[0, 1]`` by the maximum (uniform) entropy ``ln n``.

    Returns 0 for a degenerate (single-outcome) distribution. With fewer than two
    outcomes entropy is undefined-as-a-fraction, so this returns 0 (no spread).
    """
    n = len(probs)
    if n < 2:
        return 0.0
    return shannon_entropy(probs) / np.log(n)


def confidence_from_entropy(probs: Sequence[float]) -> float:
    """Confidence ``= 1 - normalized_entropy`` for a categorical distribution."""
    return 1.0 - normalized_entropy(probs)


def scenario_confidence(scenario_set: ScenarioSet) -> float:
    """Confidence in a :class:`ScenarioSet`'s posterior, from its prior weights.

    Concentrated posterior → high confidence; near-uniform → low confidence. This
    is the metric that rises as consistent observations sharpen beliefs and falls
    when contradictory observations spread them.
    """
    return confidence_from_entropy([s.prior for s in scenario_set.scenarios])


def confidence_from_variance(std: float, *, scale: float) -> float:
    """Confidence in a continuous estimate from its spread, in ``[0, 1]``.

    Uses ``1 / (1 + (std / scale)²)``: confidence is 1 at zero spread and decays
    smoothly as the standard deviation grows relative to ``scale`` (the spread you
    consider "one unit of doubt" for this quantity). Monotonically decreasing in
    ``std`` — higher variance always means lower confidence.
    """
    if scale <= 0.0:
        raise ValueError("scale must be > 0 (it sets the reference spread).")
    ratio = std / scale
    return float(1.0 / (1.0 + ratio * ratio))


def distribution_confidence(dist: ProbabilityDistribution, *, scale: float) -> float:
    """Confidence in a :class:`ProbabilityDistribution`, from its ``std``."""
    return confidence_from_variance(dist.std, scale=scale)


def posterior_mixture_risk(
    scenario_set: ScenarioSet, scenario_risk: Mapping[str, float]
) -> float:
    """Prior-weighted mean risk: ``Σ priorₛ · riskₛ`` over the scenario set.

    Collapses per-scenario risk means (from a :class:`SimulationRun`) into a single
    headline number under the current (prior or posterior) beliefs — the "fire risk
    is now X%" figure. Scenarios absent from ``scenario_risk`` contribute 0.
    """
    return float(
        sum(s.prior * scenario_risk.get(s.id, 0.0) for s in scenario_set.scenarios)
    )


if __name__ == "__main__":
    # ponytail: self-check on the confidence direction — the property that matters.
    assert confidence_from_entropy([1.0, 0.0, 0.0]) == 1.0  # certain → max confidence
    assert abs(confidence_from_entropy([1 / 3, 1 / 3, 1 / 3])) < 1e-9  # uniform → 0
    assert confidence_from_entropy([0.8, 0.1, 0.1]) > confidence_from_entropy([0.4, 0.3, 0.3])
    assert confidence_from_variance(0.0, scale=1.0) == 1.0
    assert confidence_from_variance(1.0, scale=1.0) > confidence_from_variance(5.0, scale=1.0)
    print("simulation.probability.uncertainty self-check OK")
