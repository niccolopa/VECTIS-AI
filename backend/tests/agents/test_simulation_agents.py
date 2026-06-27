"""Tests for the Session-11 Simulation Analysis Board (LLM agents over V2 output).

All LLM calls are mocked — no real OpenAI/Anthropic traffic. Covers:
- the compiled report matches the Pydantic schema,
- the LangGraph state flows Analyst → Scenario → Debate → Critic,
- the **Math Firewall**: a lying LLM cannot change the engine's numbers,
- assembling a report from a real ``RegionTwin``, and the manual API trigger.
"""

from __future__ import annotations

from typing import Any

import pytest

from vectis.agents.board.nodes import run_analyst
from vectis.agents.board.schemas import (
    BoardInput,
    DecisionIntelligenceReport,
    ScenarioView,
)
from vectis.agents.board.service import SimulationBoardService
from vectis.agents.llm.base import LLMProvider, NarrationResult
from vectis.core.schemas import RiskBand
from vectis.digital_twin.entities.region import RegionTwin


class _SpyLLM(LLMProvider):
    """Records the prompts it saw and returns the deterministic fallback (like mock)."""

    name = "spy"

    def __init__(self) -> None:
        self.instructions: list[str] = []

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        self.instructions.append(instruction)
        return NarrationResult(text=fallback, used_llm=False)


class _LyingLLM(LLMProvider):
    """A hostile model that tries to smuggle a bogus number into every narration."""

    name = "liar"

    def narrate(self, *, instruction: str, context: dict[str, Any], fallback: str,
                max_tokens: int = 600) -> NarrationResult:
        return NarrationResult(text="Actually the real risk is 12/100 at 99% confidence.", used_llm=True)


@pytest.fixture
def board_input() -> BoardInput:
    return BoardInput(
        region="liguria",
        risk_score=94.0,
        confidence=0.71,
        risk_band=RiskBand.from_score(94.0),
        primary_driver="Temperature & rainfall anomaly",
        scenarios=[
            ScenarioView(id="baseline", name="Baseline", description="Current conditions persist.", probability=0.06),
            ScenarioView(id="hotter_drier", name="Hotter & Drier", description="Heatwave deepens.", probability=0.92),
            ScenarioView(id="extreme_wind", name="Extreme Wind", description="Sustained high winds.", probability=0.02),
        ],
    )


# ── Schema / end-to-end ──────────────────────────────────────────────────────
def test_report_matches_schema(board_input):
    report = SimulationBoardService(llm=_SpyLLM()).analyze(board_input)
    assert isinstance(report, DecisionIntelligenceReport)
    # round-trips through JSON (frontend-consumable).
    assert DecisionIntelligenceReport.model_validate(report.model_dump()) == report
    assert len(report.scenarios) == 3
    assert report.debate.optimist_case and report.debate.pessimist_case
    assert report.red_team.blind_spots
    assert report.classification.startswith("VECTIS")


def test_all_agents_were_prompted(board_input):
    spy = _SpyLLM()
    SimulationBoardService(llm=spy).analyze(board_input)
    # analyst + 3 scenarios + optimist + pessimist + critic = 7 narrations.
    assert len(spy.instructions) == 7
    joined = "\n".join(spy.instructions)
    assert "MATH FIREWALL" in joined  # every prompt carries the firewall preamble


# ── LangGraph state flow ─────────────────────────────────────────────────────
def test_langgraph_state_flows_analyst_to_critic(board_input):
    pytest.importorskip("langgraph")
    from vectis.agents.board.team import build_board_graph

    final = build_board_graph(_SpyLLM()).invoke({"inp": board_input})
    # Each node populated its channel, in dependency order.
    assert final["analyst"].risk_score == 94.0
    assert len(final["scenarios"]) == 3
    assert final["debate"].optimist_case and final["debate"].pessimist_case
    assert final["red_team"].residual_uncertainty_pct == pytest.approx(29.0)


def test_graph_and_sequential_agree(board_input):
    pytest.importorskip("langgraph")
    from vectis.agents.board.team import build_board_graph

    graph = build_board_graph(_SpyLLM()).invoke({"inp": board_input})
    seq = SimulationBoardService(llm=_SpyLLM())._run_sequential(board_input)
    assert graph["analyst"] == seq["analyst"]
    assert graph["scenarios"] == seq["scenarios"]
    assert graph["debate"] == seq["debate"]
    assert graph["red_team"] == seq["red_team"]


# ── Math Firewall ────────────────────────────────────────────────────────────
def test_math_firewall_numbers_survive_a_lying_llm(board_input):
    report = SimulationBoardService(llm=_LyingLLM()).analyze(board_input)
    # The LLM said 12/100 @ 99%; the structured figures stay the engine's truth.
    assert report.analyst.risk_score == 94.0
    assert report.analyst.confidence_pct == 71.0
    assert report.red_team.residual_uncertainty_pct == pytest.approx(29.0)
    assert [s.probability_pct for s in report.scenarios] == [6.0, 92.0, 2.0]


def test_analyst_copies_figures_not_model_text(board_input):
    brief = run_analyst(board_input, _LyingLLM())
    assert brief.risk_score == 94.0 and brief.confidence_pct == 71.0  # not 12 / 99


# ── Integration with a real RegionTwin + the API ─────────────────────────────
def test_analyze_twin_from_region_twin():
    twin = RegionTwin("liguria")
    report = SimulationBoardService(llm=_SpyLLM()).analyze_twin(twin)
    assert report.region == "liguria"
    assert report.analyst.risk_score == twin.computed_risk_state.risk
    assert len(report.source.scenarios) == 3


def test_api_generate_report(client):
    res = client.post("/api/v1/intelligence/reports", json={"region": "liguria"})
    assert res.status_code == 200
    body = res.json()
    assert body["region"] == "liguria"
    assert body["analyst"]["summary"]
    assert len(body["scenarios"]) == 3
    assert body["red_team"]["blind_spots"]


def test_api_unknown_region_returns_404(client):
    assert client.post("/api/v1/intelligence/reports", json={"region": "atlantis"}).status_code == 404
