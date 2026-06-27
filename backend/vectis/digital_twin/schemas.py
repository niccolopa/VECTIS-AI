"""Digital Twin output contracts.

:class:`RiskState` is a twin's *computed* risk picture — the reduced output of the
probability engine, weighted by the twin's current beliefs. ``TwinUpdate`` is what
:meth:`DigitalTwin.update_from_observation` returns: the new risk state plus how
much beliefs moved and whether a full Monte Carlo re-run was performed.

These live in the ``digital_twin`` layer (not ``streaming``) because they are the
twin's *domain* output; the streaming layer wraps :class:`RiskState` in a
transport-level ``StateChange`` for broadcast. Pure data — no computation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from vectis.core.schemas import RiskBand


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RiskState(BaseModel):
    """A twin's current real-time risk picture after the latest update."""

    region: str
    risk: float = Field(description="Posterior-weighted risk score, 0–100.")
    band: RiskBand
    confidence: float = Field(ge=0.0, le=1.0)
    scenario_priors: dict[str, float] = Field(
        default_factory=dict, description="Current (posterior) belief over scenarios."
    )
    updated_at: datetime = Field(default_factory=_utcnow)


class TwinUpdate(BaseModel):
    """Result of applying one observation to a twin."""

    twin_id: str
    risk_state: RiskState
    belief_shift: float = Field(
        ge=0.0, description="Total-variation distance between prior and posterior beliefs."
    )
    recomputed: bool = Field(
        description="Whether a full Monte Carlo re-run was performed this update."
    )
