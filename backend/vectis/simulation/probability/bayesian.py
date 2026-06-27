"""Bayesian updating interface.

When new real-world data arrives (a fresh FIRMS detection, an updated weather
observation), our belief about *which future is unfolding* should shift. A
:class:`BayesianUpdater` performs that revision: given a prior
:class:`ScenarioSet` and an :class:`Observation`, it returns a posterior
:class:`ScenarioSet` whose priors have been re-weighted by how well each scenario
predicted the observation.

This is the engine's *learning* loop. It is pure Bayes (``scipy``) — **no LLM
ever touches this probability math.** The contract is the :class:`BayesianUpdater`
ABC; the concrete :class:`GaussianBayesianUpdater` below implements it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, Field
from scipy.stats import norm

from vectis.simulation.schemas import (
    DistributionFamily,
    Scenario,
    ScenarioSet,
    WorldState,
)


class Observation(BaseModel):
    """A real-world measurement used to update scenario beliefs.

    Maps an observed quantity (by the same variable name used in the
    :class:`~vectis.simulation.schemas.WorldState`) to its measured value and
    optional measurement uncertainty, so the updater can weight the likelihood.
    """

    variable: str
    value: float
    std: float | None = Field(default=None, ge=0.0)


class BayesianUpdater(ABC):
    """Revise scenario priors into posteriors given new evidence.

    Posterior ∝ prior × likelihood(observation | scenario). The returned
    :class:`ScenarioSet` is re-normalized (priors sum to 1), so it can feed
    straight back into the next :class:`MonteCarloEngine` run — closing the
    estimate → simulate → observe → update loop.
    """

    #: Stable identifier used in update provenance.
    name: str = "bayesian_updater"

    @abstractmethod
    def update(self, prior: ScenarioSet, observation: Observation) -> ScenarioSet:
        """Return the posterior scenario set after incorporating ``observation``.

        Args:
            prior: Current beliefs over futures (priors sum to 1).
            observation: New real-world evidence.

        Returns:
            A re-normalized posterior :class:`ScenarioSet`.
        """
        raise NotImplementedError


class GaussianBayesianUpdater(BayesianUpdater):
    r"""Closed-form Bayesian update with a Gaussian observation likelihood.

    Each scenario predicts a value for the observed variable — the base state
    estimate plus the scenario's perturbation. The likelihood of an observation
    under a scenario is the Gaussian density of the observed value at that
    prediction::

        P(obs | scenario) = N(obs.value ; mean=predicted, sigma)
        sigma = hypot(model_std, observation.std)

    and Bayes' theorem gives the posterior::

        P(scenario | obs) = P(obs | scenario) · P(scenario) / P(obs)
        P(obs)           = Σ_s P(obs | s) · P(s)        ← the evidence (denominator)

    The evidence is handled exactly: we normalize over the scenario set, so the
    returned priors sum to 1 by construction. Computation is done in log-space
    (stabilized by subtracting the max log-posterior before exponentiating) so a
    sharp observation can drive a likelihood to ~0 without underflowing to a
    degenerate all-zero posterior.

    The updater is constructed with the :class:`WorldState` because the contract
    method ``update(prior, observation)`` carries no state — yet the predicted
    value of a variable depends on the state estimate and each scenario's
    perturbation of it.
    """

    name = "gaussian_bayesian_updater"

    def __init__(self, state: WorldState, *, default_model_std: float = 1.0) -> None:
        """Args:
        state: The estimated world state the scenarios perturb.
        default_model_std: Model uncertainty (in the variable's natural units)
            used when the underlying state variable carries no usable ``std``
            (e.g. ``DETERMINISTIC``/``POISSON``/``LOGNORMAL`` variables, whose
            ``std`` is not a natural-space standard deviation). Must be > 0.
        """
        if default_model_std <= 0.0:
            raise ValueError("default_model_std must be > 0 (it is a Gaussian scale).")
        self._state = state
        self._default_model_std = float(default_model_std)

    # ── public API ───────────────────────────────────────────────────────────
    def update(self, prior: ScenarioSet, observation: Observation) -> ScenarioSet:
        """Posterior after a single observation (see :meth:`update_batch`)."""
        return self.update_batch(prior, [observation])

    def update_batch(
        self, prior: ScenarioSet, observations: Sequence[Observation]
    ) -> ScenarioSet:
        """Joint posterior after several conditionally-independent observations.

        Log-likelihoods sum across observations, so the result is independent of
        the order they arrive in (a true joint update, not a lossy sequence of
        rounded single updates). Consistent observations concentrate the
        posterior; contradictory ones flatten it.
        """
        scenarios = prior.scenarios
        if not scenarios or not observations:
            return prior

        # log P(s) — a zero prior stays zero (log → -inf, exp → 0), which is the
        # correct Bayesian behavior; silence the expected divide warning.
        with np.errstate(divide="ignore"):
            log_post = np.log(np.array([s.prior for s in scenarios], dtype=float))
        for obs in observations:
            log_post = log_post + self._log_likelihoods(scenarios, obs)

        # Stable softmax normalization → exact sum-to-1 for the ScenarioSet guard.
        log_post -= log_post.max()
        posterior = np.exp(log_post)
        posterior /= posterior.sum()

        return ScenarioSet(
            scenarios=[
                s.model_copy(update={"prior": float(p)})
                for s, p in zip(scenarios, posterior, strict=True)
            ]
        )

    # ── internals ────────────────────────────────────────────────────────────
    def _log_likelihoods(
        self, scenarios: list[Scenario], observation: Observation
    ) -> np.ndarray:
        """Vectorized log P(observation | scenario) across the scenario set."""
        base = self._state.variable(observation.variable)
        base_value = base.value if base is not None else 0.0

        # Model uncertainty: trust the state variable's std only when it is a
        # natural-space Gaussian scale; otherwise fall back to the configured default.
        if base is not None and base.family == DistributionFamily.NORMAL and base.std:
            model_std = base.std
        else:
            model_std = self._default_model_std
        sigma = float(np.hypot(model_std, observation.std or 0.0))

        predicted = np.array(
            [base_value + s.perturbations.get(observation.variable, 0.0) for s in scenarios],
            dtype=float,
        )
        return np.asarray(norm.logpdf(observation.value, loc=predicted, scale=sigma), dtype=float)


if __name__ == "__main__":
    # Liguria wildfire update use case (Session 8). Pure math, no LLM.
    from vectis.simulation.engine.runner import VectorizedMonteCarloEngine
    from vectis.simulation.probability.uncertainty import (
        posterior_mixture_risk,
        scenario_confidence,
    )
    from vectis.simulation.scenarios.generator import (
        WildfireScenarioGenerator,
        liguria_wildfire_state,
    )
    from vectis.simulation.schemas import SimulationConfig

    state = liguria_wildfire_state()
    prior = WildfireScenarioGenerator().generate(state)

    # New incoming data: a weather station reports a temperature spike to +3.5 °C,
    # well above the estimated +2.0 °C mean — evidence for the "hotter & drier" branch.
    # (ponytail: the brief also names "wind = 45 km/h"; at exactly the midpoint between
    #  the baseline 35 and extreme-wind 55 predictions it is non-discriminating, so the
    #  temperature spike from the Example Flow is used as the informative observation.)
    observation = Observation(variable="temp_anomaly_c", value=3.5, std=0.3)

    updater = GaussianBayesianUpdater(state)
    posterior = updater.update(prior, observation)

    engine = VectorizedMonteCarloEngine()
    cfg = SimulationConfig(n_iterations=50_000, seed=7)
    outcomes = {o.scenario_id: o.risk.mean for o in engine.run(state, prior, cfg).outcomes}

    print("Liguria wildfire — Bayesian update")
    print(f"  observation: temp_anomaly_c = {observation.value} °C (est. mean 2.0)\n")
    print("  scenario        prior  ->  posterior")
    for ps, qs in zip(prior.scenarios, posterior.scenarios, strict=True):
        print(f"    {ps.id:<14} {ps.prior:5.2f}  ->  {qs.prior:5.2f}")

    prior_risk = posterior_mixture_risk(prior, outcomes)
    post_risk = posterior_mixture_risk(posterior, outcomes)
    print(f"\n  fire risk (prior-weighted):     {prior_risk:5.1f} / 100")
    print(f"  fire risk (posterior-weighted): {post_risk:5.1f} / 100")
    print(f"  confidence: {scenario_confidence(prior):.0%}  ->  {scenario_confidence(posterior):.0%}")
