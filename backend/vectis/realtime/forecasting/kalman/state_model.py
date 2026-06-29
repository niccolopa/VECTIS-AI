"""Versioned cell state that carries uncertainty — the Kalman upgrade of WorldCellState.

Session 19's :class:`~vectis.realtime.state.models.WorldCellState` stores each variable
as a bare scalar. A Kalman filter needs the variable's *belief*: a ``(mean, variance)``
pair. Rather than disrupt the working EMA model and its store/tests, this is a **parallel**
state model — same versioning/provenance contract, but every variable is a
:class:`VariableEstimate` instead of a float.

Variables are held in a single ``estimates`` mapping keyed by canonical name (not fixed
fields) so any observed variable — the four climate ones or a new feed — gets a Gaussian
belief uniformly. Pure data container; the math lives in :mod:`.filter`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from vectis.realtime.events.base import CellId


def _utcnow() -> datetime:
    return datetime.now(UTC)


class VariableEstimate(BaseModel):
    """One variable's Gaussian belief: best estimate plus the uncertainty around it."""

    mean: float = Field(description="Best current estimate of the variable.")
    variance: float = Field(ge=0.0, description="Uncertainty (σ²) of the estimate; drops as data agrees.")


class KalmanCellState(BaseModel):
    """A grid cell's per-variable Gaussian beliefs, versioned for auditable replay.

    ``version`` increments and ``last_updated`` stamps on every applied observation;
    ``last_updated`` is set to the observation's ``observed_at`` so the next prediction
    can grow uncertainty by the real elapsed time between readings.
    """

    cell_id: CellId = Field(description="Grid cell this state describes.")
    estimates: dict[str, VariableEstimate] = Field(
        default_factory=dict, description="Canonical variable name → its Gaussian belief."
    )
    version: int = Field(default=0, ge=0, description="Monotonic revision; +1 per observation.")
    last_updated: datetime = Field(default_factory=_utcnow, description="When this version was written.")
    sources: list[str] = Field(default_factory=list, description="Feeds that have shaped this cell.")
