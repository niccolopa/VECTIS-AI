"""ContinuousBayesianUpdater — turn a live Kalman state into live scenario probabilities.

This is the V3 streaming adaptation of the V2 on-demand
:class:`~vectis.simulation.probability.bayesian.GaussianBayesianUpdater`. Where V2 took a
prior + a discrete observation and returned a one-shot posterior, this updater **carries**
its belief between ticks: every corrected :class:`~vectis.realtime.forecasting.kalman.state_model.KalmanCellState`
from Session 20 produces a posterior that becomes the prior for the next tick.

One tick of :meth:`update_probabilities`:

1. **relax** the held prior a touch toward its baseline (time-scaled) — the anti-lock-in
   step from :class:`~vectis.realtime.forecasting.bayesian.priors.ScenarioPriors`;
2. score each scenario's **log-likelihood** of the current Kalman state;
3. ``log posterior = log prior + log likelihood``, then a **stable softmax** (subtract the
   max before exponentiating) gives an exact normalized posterior — the evidence sum
   ``Σ prior·likelihood`` is the softmax denominator, computed exactly over the finite
   scenario set;
4. **store** the posterior as the new prior and return it.

Pure arithmetic, no LLM, no transport — a stream consumer calls ``update_probabilities``
with each state change and is free to publish the result however it likes. The Math
Firewall holds.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from vectis.realtime.forecasting.bayesian.likelihood import ScenarioProfile, log_likelihoods
from vectis.realtime.forecasting.bayesian.priors import ScenarioPriors, normalize
from vectis.realtime.forecasting.kalman.state_model import KalmanCellState


class ContinuousBayesianUpdater:
    """Streaming Bayesian filter: corrected Kalman state → posterior scenario probabilities.

    :param profiles: scenario_id → :class:`ScenarioProfile`. Must match the prior's scenarios.
    :param priors: the carried belief; mutated in place each tick (posterior → next prior).
    :param default_spread: per-variable σ used for any variable a profile leaves unspecified.
    """

    def __init__(
        self,
        profiles: Mapping[str, ScenarioProfile],
        priors: ScenarioPriors,
        *,
        default_spread: float = 1.0,
    ) -> None:
        if default_spread <= 0.0:
            raise ValueError("default_spread must be positive (it is a Gaussian scale)")
        if set(profiles) != set(priors.scenarios):
            raise ValueError("profiles must cover exactly the scenarios held in the priors")
        self._profiles = dict(profiles)
        self._priors = priors
        self._default_spread = default_spread

    @property
    def probabilities(self) -> dict[str, float]:
        """The current belief without advancing the filter."""
        return self._priors.probabilities

    def update_probabilities(
        self, state: KalmanCellState, *, elapsed_seconds: float = 1.0
    ) -> dict[str, float]:
        """Fold one Kalman state into the belief and return the new posterior.

        ``elapsed_seconds`` scales the prior relaxation (time since the last tick).
        """
        prior = self._priors.relax(elapsed_seconds=elapsed_seconds)
        log_like = log_likelihoods(self._profiles, state, default_spread=self._default_spread)

        # log posterior = log prior + log likelihood, over the scenarios in prior order.
        scenarios = list(prior)
        log_post = [math.log(prior[s]) + log_like[s] for s in scenarios]

        # Stable softmax: subtract the max before exp so a sharp likelihood can't underflow.
        peak = max(log_post)
        weights = {s: math.exp(lp - peak) for s, lp in zip(scenarios, log_post, strict=True)}
        posterior = normalize(weights)

        self._priors.set(posterior)
        return self._priors.probabilities


if __name__ == "__main__":
    # Continuous fire-risk update (Session 21). Pure math, no LLM.
    from vectis.realtime.forecasting.kalman.state_model import VariableEstimate

    profiles = {
        "baseline": ScenarioProfile(
            scenario_id="baseline",
            expected={"drought_index": 0.30, "wind_speed": 20.0},
            spread={"drought_index": 0.35, "wind_speed": 15.0},
        ),
        "fire": ScenarioProfile(
            scenario_id="fire",
            expected={"drought_index": 0.70, "wind_speed": 40.0},
            spread={"drought_index": 0.35, "wind_speed": 15.0},
        ),
    }
    priors = ScenarioPriors(
        {"baseline": 0.55, "fire": 0.45},
        baseline={"baseline": 0.5, "fire": 0.5},
        relax_rate=0.0,
    )
    updater = ContinuousBayesianUpdater(profiles, priors)

    drought_state = KalmanCellState(
        cell_id="44.4,8.9",
        estimates={
            "drought_index": VariableEstimate(mean=0.65, variance=0.01),
            "wind_speed": VariableEstimate(mean=35.0, variance=4.0),
        },
    )
    print(f"  prior fire risk:     {priors.probabilities['fire']:.0%}")
    posterior = updater.update_probabilities(drought_state)
    print("  observe: severe drought (0.65) + high wind (35 km/h)")
    print(f"  posterior fire risk: {posterior['fire']:.0%}")
