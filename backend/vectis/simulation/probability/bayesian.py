"""Bayesian updating interface.

When new real-world data arrives (a fresh FIRMS detection, an updated weather
observation), our belief about *which future is unfolding* should shift. A
:class:`BayesianUpdater` performs that revision: given a prior
:class:`ScenarioSet` and an :class:`Observation`, it returns a posterior
:class:`ScenarioSet` whose priors have been re-weighted by how well each scenario
predicted the observation.

This is the engine's *learning* loop. It is pure Bayes (``scipy``/``pymc`` when
implemented) — **no LLM ever touches this probability math.** Implementation is
deferred to Session 7; this file fixes the contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from vectis.simulation.schemas import ScenarioSet


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
