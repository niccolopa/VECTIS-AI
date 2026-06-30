"""Integration tests for the multi-agent orchestrator."""

from __future__ import annotations

import pytest

from vectis.agents.orchestrator import Orchestrator
from vectis.core.schemas import AnalysisRequest

pytestmark = pytest.mark.integration


def test_full_pipeline_produces_report() -> None:
    report = Orchestrator().run(AnalysisRequest(region="california"))
    assert 0 <= report.risk_score <= 100
    assert report.drivers, "report must explain its score with drivers"
    assert report.recommended_actions
    assert report.cell_risks
    assert report.model_card_ref


def test_all_six_agents_run() -> None:
    report = Orchestrator().run(AnalysisRequest(region="california"))
    agents = {t.agent for t in report.trace}
    assert agents == {
        "data_discovery", "data_analyst", "ml_research",
        "simulation", "report", "critic",
    }


def test_critic_reviews_every_report() -> None:
    report = Orchestrator().run(AnalysisRequest(region="california"))
    # The Critic is mandatory: a verdict is always present.
    assert report.critic_review is not None
    # Every headline driver must be backed by evidence (Critic invariant).
    metrics = {e.metric for e in report.evidence if e.metric}
    text = " ".join(e.statement.lower() for e in report.evidence)
    for d in report.drivers:
        assert d.feature in metrics or d.name.lower() in text


def test_mock_provider_is_deterministic() -> None:
    a = Orchestrator().run(AnalysisRequest(region="california"))
    b = Orchestrator().run(AnalysisRequest(region="california"))
    assert a.risk_score == b.risk_score
    assert a.summary == b.summary
    assert [d.name for d in a.drivers] == [d.name for d in b.drivers]
