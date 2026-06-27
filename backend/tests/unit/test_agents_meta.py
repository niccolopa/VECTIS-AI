"""Agent system metadata + assembly tests (no model/data required)."""

from __future__ import annotations

from vectis.agents.orchestrator import Orchestrator, get_orchestrator
from vectis.agents.runtime import AgentSuite, BaseOrchestrator


def test_suite_builds_six_agents() -> None:
    suite = AgentSuite.build()
    agents = [suite.discovery, suite.analyst, suite.ml_research,
              suite.simulation, suite.report, suite.critic]
    assert len(agents) == 6
    # The four pre-report stages run before the Report⟲Critic pair.
    assert len(suite.evidence_stages) == 4


def test_every_agent_declares_a_responsibility() -> None:
    suite = AgentSuite.build()
    for agent in (suite.discovery, suite.analyst, suite.ml_research,
                  suite.simulation, suite.report, suite.critic):
        assert agent.name and agent.name != "agent"
        assert agent.responsibility, f"{agent.name} must declare a responsibility"


def test_agent_names_are_unique() -> None:
    suite = AgentSuite.build()
    names = [a.name for a in (suite.discovery, suite.analyst, suite.ml_research,
                              suite.simulation, suite.report, suite.critic)]
    assert len(names) == len(set(names))


def test_factory_defaults_to_custom_engine() -> None:
    # conftest does not set VECTIS_ORCHESTRATOR, so the default applies.
    orch = get_orchestrator()
    assert isinstance(orch, Orchestrator)
    assert isinstance(orch, BaseOrchestrator)
