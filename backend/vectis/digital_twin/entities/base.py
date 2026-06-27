"""The :class:`DigitalTwin` abstract base class.

Every twin — climate region today, a financial market tomorrow — implements this
small, uniform interface so the rest of the system (streaming, API, future agents)
can treat any twin identically:

- :meth:`get_current_state` — read the twin's physical state (a typed snapshot).
- :meth:`update_from_observation` — evolve the twin with one new observation
  (deterministic transition + Bayesian belief update + risk recompute).
- :meth:`predict_risk` — ask the probability engine for the twin's current risk.

The ABC is intentionally tiny and **carries no calculator**: *how* a twin maps its
domain state onto the generic Monte Carlo / Bayesian engines is the concrete
twin's business logic. That separation is what lets a ``FinancialMarketTwin`` reuse
the exact same engines with a completely different state and transition model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from vectis.digital_twin.schemas import RiskState, TwinUpdate
from vectis.simulation.probability.bayesian import Observation


class TwinState(BaseModel):
    """Marker base for a twin's physical state snapshot.

    Concrete twins subclass this with their own fields (a region's temperature,
    a market's volatility…). Keeping a shared base lets :meth:`DigitalTwin.
    get_current_state` be typed uniformly while each twin stays strongly typed.
    """


class DigitalTwin(ABC):
    """A stateful, self-updating model of one real-world entity."""

    #: Unique id within the :class:`~vectis.digital_twin.state.manager.StateManager`.
    twin_id: str
    #: Coarse type tag (e.g. ``"region"``, ``"financial_market"``) for routing/UX.
    kind: str = "twin"

    @abstractmethod
    def get_current_state(self) -> TwinState:
        """Return a snapshot of the twin's current physical state."""
        raise NotImplementedError

    @abstractmethod
    def update_from_observation(self, observation: Observation) -> TwinUpdate:
        """Evolve the twin with one observation and return the new risk picture.

        Concrete twins implement the template: apply deterministic
        :mod:`~vectis.digital_twin.transitions` to the physical state, run the
        Bayesian belief update, then (if warranted) recompute risk via Monte Carlo.
        """
        raise NotImplementedError

    @abstractmethod
    def predict_risk(self) -> RiskState:
        """Compute and return the twin's current risk state from the engine."""
        raise NotImplementedError
