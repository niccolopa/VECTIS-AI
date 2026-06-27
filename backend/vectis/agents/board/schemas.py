"""Structured contracts for the Simulation Analysis Board.

The board's input is :class:`BoardInput` (the engine numbers, the firewall's source
of truth); its output is :class:`DecisionIntelligenceReport` — a fully-typed,
JSON-serializable brief the frontend can render directly (no wall of text).

Every numeric field here is *copied from the engine*, never produced by an LLM.
The LLM fills only the prose fields (``summary``, ``storyline``, ``*_case``,
``challenge``). That split is the Math Firewall expressed in the type system.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from vectis.core.schemas import RiskBand


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _report_id() -> str:
    return "dir_" + uuid.uuid4().hex[:12]


# ── Input: the authoritative engine numbers ──────────────────────────────────
class ScenarioView(BaseModel):
    """One statistical scenario, as the board receives it (read-only numbers)."""

    id: str
    name: str
    description: str
    probability: float = Field(ge=0.0, le=1.0, description="Posterior weight of this branch.")


class BoardInput(BaseModel):
    """The engine's verdict the board analyzes — the Math Firewall's source of truth."""

    region: str
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    risk_band: RiskBand
    primary_driver: str
    scenarios: list[ScenarioView] = Field(default_factory=list)


# ── Per-agent outputs ────────────────────────────────────────────────────────
class AnalystBrief(BaseModel):
    """Executive summary from the Analyst. Prose + copied figures."""

    summary: str
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence_pct: float = Field(ge=0.0, le=100.0)
    risk_band: RiskBand
    primary_driver: str


class ScenarioNarrative(BaseModel):
    """A statistical scenario translated into a human-readable storyline."""

    scenario_id: str
    name: str
    probability_pct: float = Field(ge=0.0, le=100.0)
    storyline: str


class DebateRound(BaseModel):
    """Opposed readings of the same numbers from the two debate sub-agents."""

    optimist_case: str
    pessimist_case: str


class RedTeamCritique(BaseModel):
    """The Red-Team critic's attack on the prediction: blind spots, residual risk."""

    challenge: str
    blind_spots: list[str] = Field(default_factory=list)
    residual_uncertainty_pct: float = Field(
        ge=0.0, le=100.0, description="100·(1 − confidence) — the unmodeled tail."
    )


class DecisionIntelligenceReport(BaseModel):
    """The compiled board output — a serious, structured intelligence brief."""

    report_id: str = Field(default_factory=_report_id)
    classification: str = "VECTIS // DECISION INTELLIGENCE"
    region: str
    generated_at: datetime = Field(default_factory=_utcnow)
    bottom_line: str = Field(description="BLUF — bottom line up front, from the numbers.")
    source: BoardInput = Field(description="The authoritative engine numbers (audit trail).")
    analyst: AnalystBrief
    scenarios: list[ScenarioNarrative] = Field(default_factory=list)
    debate: DebateRound
    red_team: RedTeamCritique
