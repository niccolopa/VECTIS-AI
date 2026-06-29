"""Bayesian Continuous Update Engine — live state → live categorical probabilities.

Session 21. The Kalman layer (Session 20) keeps each cell's *physical* variables
continuously estimated with uncertainty; this layer translates that stream into
continuously-updated **categorical** beliefs — the probability of each scenario/outcome
(e.g. baseline vs. disaster), revised on every state change.

It is the streaming counterpart of the V2 on-demand
:class:`~vectis.simulation.probability.bayesian.GaussianBayesianUpdater`: priors are
*carried* between ticks (each posterior is the next prior) and relax toward a baseline so
the belief can never lock at a hard 0/100 that a future observation couldn't reverse.

Three pieces, decoupled from any stream transport so event consumers can call them safely:

- :class:`ScenarioProfile` / :func:`log_likelihood` — how well a Kalman state matches a
  scenario archetype, in log-space;
- :class:`ScenarioPriors` — the carried, relaxing categorical belief;
- :class:`ContinuousBayesianUpdater` — ``update_probabilities(kalman_state) -> posterior``.

Pure arithmetic, no LLM — the Math Firewall holds.
"""

from __future__ import annotations

from vectis.realtime.forecasting.bayesian.likelihood import (
    ScenarioProfile,
    log_likelihood,
    log_likelihoods,
)
from vectis.realtime.forecasting.bayesian.priors import ScenarioPriors, normalize
from vectis.realtime.forecasting.bayesian.updater import ContinuousBayesianUpdater

__all__ = [
    "ContinuousBayesianUpdater",
    "ScenarioPriors",
    "ScenarioProfile",
    "log_likelihood",
    "log_likelihoods",
    "normalize",
]
