"""Scenario generation interface.

A :class:`ScenarioGenerator` turns the current :class:`WorldState` into a
:class:`ScenarioSet`: a set of weighted, mutually-exclusive hypotheses about how
the future could unfold. This is the *branching* step — it decides **which**
futures the Monte Carlo engine will explore and **how likely** each is a priori.

No statistics happen here beyond assigning priors; the heavy sampling is the
engine's job. Generators are deterministic given the same state and seed, so runs
are reproducible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vectis.simulation.schemas import ScenarioSet, WorldState


class ScenarioGenerator(ABC):
    """Produce a weighted set of future hypotheses from the current state.

    Implementations might branch on climate trajectories (hotter/drier vs. wetter),
    wind events, or data-driven regimes. Whatever the strategy, the returned
    :class:`ScenarioSet` must be a valid probability distribution (priors sum to 1
    — enforced by the schema), so downstream outputs are true probabilities.
    """

    #: Stable identifier used in traces and forecast provenance.
    name: str = "scenario_generator"

    @abstractmethod
    def generate(self, state: WorldState) -> ScenarioSet:
        """Branch ``state`` into a normalized :class:`ScenarioSet`.

        Args:
            state: The digital-twin estimate of the world now (the initial
                condition every scenario perturbs).

        Returns:
            A :class:`ScenarioSet` whose scenario priors sum to 1.0.
        """
        raise NotImplementedError
