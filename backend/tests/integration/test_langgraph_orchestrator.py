"""LangGraph engine tests: parity with the custom engine over the same agents.

Skipped automatically if the optional ``langgraph`` dependency is not installed,
so the suite stays green on a lean install.
"""

from __future__ import annotations

import pytest

from vectis.agents.orchestrator import Orchestrator
from vectis.agents.runtime import BaseOrchestrator
from vectis.core.schemas import AnalysisRequest

pytest.importorskip("langgraph")
pytestmark = pytest.mark.integration

from vectis.agents.langgraph_engine import LangGraphOrchestrator  # noqa: E402

REGION = AnalysisRequest(region="liguria")


def test_langgraph_runs_all_six_agents() -> None:
    report = LangGraphOrchestrator().run(REGION)
    agents = [t.agent for t in report.trace]
    assert agents == [
        "data_discovery", "data_analyst", "ml_research",
        "simulation", "report", "critic",
    ]


def test_langgraph_satisfies_orchestrator_interface() -> None:
    assert isinstance(LangGraphOrchestrator(), BaseOrchestrator)


def test_langgraph_matches_custom_engine() -> None:
    custom = Orchestrator().run(REGION)
    graph = LangGraphOrchestrator().run(REGION)
    # The engines wrap identical agents, so results must match exactly.
    assert graph.risk_score == custom.risk_score
    assert graph.confidence == custom.confidence
    assert [d.name for d in graph.drivers] == [d.name for d in custom.drivers]
    assert graph.critic_review.approved == custom.critic_review.approved


def test_langgraph_report_is_critic_reviewed() -> None:
    report = LangGraphOrchestrator().run(REGION)
    assert report.critic_review is not None
    metrics = {e.metric for e in report.evidence if e.metric}
    text = " ".join(e.statement.lower() for e in report.evidence)
    for d in report.drivers:
        assert d.feature in metrics or d.name.lower() in text
