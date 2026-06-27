"""Monte Carlo simulation runner interface.

The :class:`MonteCarloEngine` is the numerical heart of V2. Given an initial
:class:`WorldState` and a :class:`ScenarioSet`, it draws ``N`` stochastic
trajectories per scenario through a stochastic model (``models/``), then reduces
the raw draws into a :class:`SimulationRun` of per-scenario
:class:`ProbabilityDistribution`s.

**The V2 Golden Rule lives here:** every number this interface produces comes
from deterministic/probabilistic libraries (``numpy``/``scipy``/``pymc``) seeded
for reproducibility — **never** from an LLM. Concrete implementations land in
Session 7; this file fixes the contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vectis.simulation.schemas import (
    ScenarioSet,
    SimulationConfig,
    SimulationRun,
    WorldState,
)


class MonteCarloEngine(ABC):
    """Execute ``N`` simulation iterations over a state × scenario set.

    The engine is the only place trajectories are sampled. It must be:
    - **Reproducible**: identical ``(state, scenarios, config.seed)`` ⇒ identical
      :class:`SimulationRun`. A seeded ``numpy`` ``Generator`` is the source of
      randomness; nothing else may introduce entropy.
    - **Pure**: no I/O, no LLMs, no agent imports — a headless math service.
    - **Vectorized**: built for high iteration counts (10k–1M draws); prefer
      array operations over Python loops in the concrete implementation.
    """

    #: Stable identifier used in run provenance.
    name: str = "monte_carlo_engine"

    @abstractmethod
    def run(
        self,
        state: WorldState,
        scenarios: ScenarioSet,
        config: SimulationConfig,
    ) -> SimulationRun:
        """Simulate ``config.n_iterations`` trajectories per scenario.

        Args:
            state: Initial condition (digital twin), with per-variable uncertainty.
            scenarios: Weighted future hypotheses to explore (priors sum to 1).
            config: Iteration count, horizon, RNG seed, sample-retention flag.

        Returns:
            A :class:`SimulationRun` with one :class:`ScenarioOutcome` per
            scenario, each holding the outcome :class:`ProbabilityDistribution`.
        """
        raise NotImplementedError
