"""Shared orchestration runtime.

Both orchestration engines — the default ``custom`` engine and the optional
``langgraph`` engine — are thin assemblers over the *same* agents and the *same*
run setup. This module holds everything they share so the two backends can never
drift apart in which agents run or how a run is initialized/finalized:

- :class:`BaseOrchestrator` — the interface the service depends on.
- :class:`AgentSuite` — the six agents, built once from an LLM provider.
- :func:`new_run` — build the initial ``AgentState`` + ``RunContext``.
- :func:`finalize` — extract the final report and attach the full trace.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from vectis.agents.analyst import AnalystAgent
from vectis.agents.base import Agent, RunContext
from vectis.agents.critic import CriticAgent
from vectis.agents.discovery import DiscoveryAgent
from vectis.agents.llm.base import LLMProvider
from vectis.agents.llm.factory import get_llm_provider
from vectis.agents.ml_research import MLResearchAgent
from vectis.agents.report import ReportAgent
from vectis.agents.simulation import SimulationAgent
from vectis.core.exceptions import AgentError
from vectis.core.schemas import AgentState, AnalysisRequest, DecisionReport
from vectis.data.connectors.base import Connector
from vectis.data.regions import get_region
from vectis.models.registry import ModelRegistry


@runtime_checkable
class BaseOrchestrator(Protocol):
    """Anything that turns an analysis request into a Decision Report.

    The seam that lets the orchestration engine be swapped (custom ↔ langgraph)
    without touching the API or service layers.
    """

    def run(self, request: AnalysisRequest) -> DecisionReport: ...


@dataclass
class AgentSuite:
    """The six VECTIS agents, sharing one LLM provider."""

    discovery: DiscoveryAgent
    analyst: AnalystAgent
    ml_research: MLResearchAgent
    simulation: SimulationAgent
    report: ReportAgent
    critic: CriticAgent

    @classmethod
    def build(cls, llm: LLMProvider | None = None) -> AgentSuite:
        llm = llm or get_llm_provider()
        return cls(
            discovery=DiscoveryAgent(llm),
            analyst=AnalystAgent(llm),
            ml_research=MLResearchAgent(llm),
            simulation=SimulationAgent(llm),
            report=ReportAgent(llm),
            critic=CriticAgent(llm),
        )

    @property
    def evidence_stages(self) -> tuple[Agent, ...]:
        """The pre-report agents, in execution order."""
        return (self.discovery, self.analyst, self.ml_research, self.simulation)


def new_run(request: AnalysisRequest, *, registry: ModelRegistry,
            connector: Connector) -> tuple[AgentState, RunContext]:
    """Build the initial mutable state and working context for a run."""
    region = get_region(request.region)
    run_id = uuid.uuid4().hex[:12]
    ctx = RunContext(region=region, connector=connector, registry=registry)
    state = AgentState(request=request, run_id=run_id)
    return state, ctx


def finalize(state: AgentState) -> DecisionReport:
    """Return the final report with the complete agent trace attached."""
    report = state.draft_report
    if report is None:  # pragma: no cover - defensive
        raise AgentError("Orchestrator finished without producing a report.")
    report.trace = list(state.trace)
    return report
