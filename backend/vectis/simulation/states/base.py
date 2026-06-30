"""State estimation interface.

A :class:`StateEstimator` builds the digital twin — the :class:`WorldState` that
every simulation starts from — out of external data and the V1 feature pipeline.
Its job is not just to report current values but to attach **uncertainty** to
each one, because honest forecasting propagates how unsure we are, not just a
best guess.

Pure data assembly + uncertainty quantification; no LLMs. Implementation lands
once live connectors (NASA FIRMS, ERA5) are wired in (Session 7+).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from vectis.simulation.schemas import WorldState


class StateEstimator(ABC):
    """Estimate the current :class:`WorldState` of a region, with uncertainty.

    Implementations turn raw/engineered features into :class:`StateVariable`s,
    choosing a :class:`DistributionFamily` and uncertainty parameters per
    variable (e.g. sensor noise → ``NORMAL`` with a measured ``std``). The output
    is the initial condition for scenario generation and Monte Carlo simulation.
    """

    #: Stable identifier used in state provenance.
    name: str = "state_estimator"

    @abstractmethod
    def estimate(self, region: str) -> WorldState:
        """Build the digital-twin state for ``region`` as of now.

        Args:
            region: Region key (e.g. ``"california"``), matching V1's region vocabulary.

        Returns:
            A :class:`WorldState` whose variables carry value + uncertainty.
        """
        raise NotImplementedError
