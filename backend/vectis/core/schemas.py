"""Domain contracts — the spine of VECTIS.

These Pydantic models are the shared vocabulary every layer agrees on:
the data pipeline produces features, the ML layer produces predictions and
SHAP-based driver attributions, the agents reason over them, and the API
returns a :class:`DecisionReport`. Changing these types is a deliberate,
reviewed act (see CONTRIBUTING.md).

Design rules:
- A ``DecisionReport`` is only valid if every claim is backed by evidence and
  the Critic has reviewed it. The schema encodes that discipline structurally.
- Scores are normalized: ``risk_score`` is 0–100, ``confidence`` is 0–1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────────
# Risk vocabulary
# ─────────────────────────────────────────────────────────────────────────────
class RiskBand(StrEnum):
    """Human-facing bucketing of a 0–100 risk score."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"

    @classmethod
    def from_score(cls, score: float) -> RiskBand:
        if score >= 75:
            return cls.SEVERE
        if score >= 50:
            return cls.HIGH
        if score >= 25:
            return cls.MODERATE
        return cls.LOW


class Direction(StrEnum):
    """Whether a driver pushes risk up or down."""

    INCREASES = "increases"
    DECREASES = "decreases"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence & explainability
# ─────────────────────────────────────────────────────────────────────────────
class Driver(BaseModel):
    """A factor influencing the risk score, attributed via SHAP.

    ``contribution`` is the signed SHAP value (in log-odds space) — its
    magnitude ranks importance, its sign gives ``direction``.
    """

    name: str
    feature: str
    value: float
    contribution: float
    direction: Direction
    description: str = ""

    @classmethod
    def from_shap(cls, feature: str, value: float, shap_value: float, label: str | None = None,
                  description: str = "") -> Driver:
        return cls(
            name=label or feature.replace("_", " ").title(),
            feature=feature,
            value=value,
            contribution=shap_value,
            direction=Direction.INCREASES if shap_value >= 0 else Direction.DECREASES,
            description=description,
        )


class Evidence(BaseModel):
    """A concrete, checkable fact supporting a claim in the report."""

    source: str
    statement: str
    metric: str | None = None
    value: float | None = None


class RecommendedAction(BaseModel):
    action: str
    rationale: str
    priority: Priority = Priority.MEDIUM


# ─────────────────────────────────────────────────────────────────────────────
# Critic
# ─────────────────────────────────────────────────────────────────────────────
class CriticIssue(BaseModel):
    """A single objection raised by the Critic agent."""

    severity: Literal["info", "warning", "blocker"]
    claim: str
    problem: str


class CriticReview(BaseModel):
    """The Critic's verdict on a draft report.

    ``approved`` is False while blockers remain. The orchestrator may ask the
    Report agent to revise up to ``Settings.critic_max_revisions`` times.
    """

    approved: bool
    revision_count: int = 0
    issues: list[CriticIssue] = Field(default_factory=list)
    notes: str = ""

    @property
    def blockers(self) -> list[CriticIssue]:
        return [i for i in self.issues if i.severity == "blocker"]


# ─────────────────────────────────────────────────────────────────────────────
# Prediction (ML layer output)
# ─────────────────────────────────────────────────────────────────────────────
class CellPrediction(BaseModel):
    """Model output for a single geographic cell."""

    cell_id: str
    lat: float
    lon: float
    probability: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=100.0)
    drivers: list[Driver] = Field(default_factory=list)


class CellRisk(BaseModel):
    """Compact per-cell risk point for map rendering (no driver detail)."""

    cell_id: str
    lat: float
    lon: float
    risk_score: float = Field(ge=0.0, le=100.0)


class RegionPrediction(BaseModel):
    """Aggregated model output for a region."""

    region: str
    model_name: str
    model_card_ref: str
    cells: list[CellPrediction]
    mean_probability: float
    aggregate_risk_score: float = Field(ge=0.0, le=100.0)
    top_drivers: list[Driver] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# The Decision Intelligence Report — the public deliverable
# ─────────────────────────────────────────────────────────────────────────────
class DecisionReport(BaseModel):
    """The explainable, human-in-the-loop output of an VECTIS analysis.

    Answers the four VECTIS questions: what is happening (summary + drivers),
    why (evidence), what could happen next (risk_score + confidence), and what
    to do (recommended_actions) — all gated by the Critic.
    """

    id: str
    region: str
    area_label: str
    generated_at: datetime = Field(default_factory=_utcnow)

    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str

    drivers: list[Driver] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    cell_risks: list[CellRisk] = Field(default_factory=list)

    critic_review: CriticReview
    model_card_ref: str
    trace: list[AgentTrace] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def risk_band(self) -> RiskBand:
        return RiskBand.from_score(self.risk_score)


# ─────────────────────────────────────────────────────────────────────────────
# Agent orchestration state
# ─────────────────────────────────────────────────────────────────────────────
class AgentTrace(BaseModel):
    """An auditable record of one agent's contribution to a run."""

    agent: str
    summary: str
    duration_ms: float = 0.0
    used_llm: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    """Inbound request to run an analysis."""

    region: str = Field(default="california", description="Region key, e.g. 'california'.")
    window_days: int = Field(default=30, ge=1, le=365)


class AgentState(BaseModel):
    """Mutable state threaded through the orchestrator DAG.

    Each agent reads the fields it needs and writes its outputs back, appending
    a :class:`AgentTrace`. The Report agent assembles ``draft_report``; the
    Critic populates ``critic_review`` and may trigger a bounded revision loop.
    """

    request: AnalysisRequest
    run_id: str

    # Filled progressively by the agents:
    region_label: str = ""
    data_summary: dict[str, Any] = Field(default_factory=dict)
    signals: list[str] = Field(default_factory=list)
    prediction: RegionPrediction | None = None
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    draft_report: DecisionReport | None = None
    critic_review: CriticReview | None = None
    revision_count: int = 0
    trace: list[AgentTrace] = Field(default_factory=list)

    def add_trace(self, trace: AgentTrace) -> None:
        self.trace.append(trace)


# Resolve forward references (AgentTrace referenced by DecisionReport).
DecisionReport.model_rebuild()
AgentState.model_rebuild()
