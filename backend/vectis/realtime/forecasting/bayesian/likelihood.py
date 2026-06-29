"""Log-likelihood of a Kalman state under a categorical scenario.

The Session-20 :class:`~vectis.realtime.forecasting.kalman.state_model.KalmanCellState`
gives each variable a Gaussian belief ``(mean, variance)``. A *scenario* (baseline vs.
disaster, etc.) is a profile of the values we'd *expect* each variable to hold if that
scenario were the true state of the world. The likelihood asks: how well does the cell's
current belief match a scenario's profile?

For one variable that is the overlap of two Gaussians — the cell's estimate and the
scenario's expectation. Their convolution is itself Gaussian, so::

    P(state_v | scenario) = N(estimate.mean ; loc=expected, scale=√(estimate.variance + spread²))

where ``spread`` is the scenario's own tolerance for that variable (how far the real
reading may sit from the archetype and still count as "this scenario"). The cell's own
uncertainty widens the scale: a fuzzy estimate discriminates between scenarios less
sharply, exactly as it should.

Independent variables ⇒ the joint log-likelihood is the **sum** of the per-variable
log-densities. Everything is computed in log-space (stdlib :mod:`math`, no scipy in the
streaming hot path) so a streaming product of many ticks never underflows.

Pure arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from pydantic import BaseModel, Field

from vectis.realtime.forecasting.kalman.state_model import KalmanCellState

_LOG_2PI = math.log(2.0 * math.pi)


class ScenarioProfile(BaseModel):
    """The archetypal variable values that define one categorical outcome.

    :param scenario_id: stable identifier (e.g. ``"baseline"`` / ``"fire"``).
    :param expected: canonical variable name → the value this scenario expects.
    :param spread: per-variable tolerance (σ) around ``expected``; defaults to
        ``default_spread`` at scoring time for any variable omitted here. Larger ⇒ the
        scenario is more forgiving of readings far from its archetype.
    """

    scenario_id: str = Field(description="Stable identifier for the scenario/outcome.")
    expected: dict[str, float] = Field(description="Variable → value this scenario expects.")
    spread: dict[str, float] = Field(
        default_factory=dict, description="Variable → tolerance σ around the expected value."
    )


def _gaussian_logpdf(x: float, *, loc: float, scale: float) -> float:
    """log N(x; loc, scale) in stdlib math — the per-variable density."""
    z = (x - loc) / scale
    return -0.5 * z * z - math.log(scale) - 0.5 * _LOG_2PI


def log_likelihood(
    profile: ScenarioProfile,
    state: KalmanCellState,
    *,
    default_spread: float = 1.0,
) -> float:
    """Joint log P(current Kalman state | scenario) over the shared variables.

    Only variables the scenario expects *and* the cell has estimated contribute — an
    unobserved variable carries no evidence (it neither favors nor rejects any scenario).
    The cell's own ``variance`` is folded into the Gaussian scale so an uncertain estimate
    discriminates less between scenarios.

    Returns ``0.0`` (a uniform, non-discriminating likelihood) when no variable overlaps.
    """
    total = 0.0
    for variable, expected in profile.expected.items():
        estimate = state.estimates.get(variable)
        if estimate is None:
            continue
        spread = profile.spread.get(variable, default_spread)
        scale = math.sqrt(estimate.variance + spread * spread)
        total += _gaussian_logpdf(estimate.mean, loc=expected, scale=scale)
    return total


def log_likelihoods(
    profiles: Mapping[str, ScenarioProfile],
    state: KalmanCellState,
    *,
    default_spread: float = 1.0,
) -> dict[str, float]:
    """Per-scenario log-likelihoods for the current state — the updater's evidence terms."""
    return {
        sid: log_likelihood(profile, state, default_spread=default_spread)
        for sid, profile in profiles.items()
    }
