"""Custom orchestration engine — the default typed DAG + Critic revision loop.

Execution order:

    Discovery → Analyst → ML Research → Simulation → Report ⟲ Critic

The pre-report agents run once, in sequence, each enriching the shared state.
The Report/Critic pair then iterates: if the Critic raises a blocker, the Report
agent revises (dropping unsupported claims) and is re-reviewed, up to
``Settings.critic_max_revisions``. Whatever the outcome, the final report
carries the Critic's verdict transparently — a human stays in control.

This engine is deterministic and dependency-light. An equivalent
:class:`~vectis.agents.langgraph_engine.LangGraphOrchestrator` expresses the same
flow as a LangGraph state machine; both implement :class:`BaseOrchestrator` and
are interchangeable via :func:`get_orchestrator` (``VECTIS_ORCHESTRATOR``).
"""

from __future__ import annotations

from vectis.agents.llm.base import LLMProvider
from vectis.agents.runtime import AgentSuite, BaseOrchestrator, finalize, new_run
from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.core.schemas import AnalysisRequest, DecisionReport
from vectis.data.connectors import get_connector
from vectis.data.connectors.base import Connector
from vectis.models.registry import ModelRegistry

log = get_logger(__name__)


class Orchestrator:
    """Runs the multi-agent pipeline for a single analysis request (custom engine)."""

    def __init__(self, llm: LLMProvider | None = None,
                 registry: ModelRegistry | None = None,
                 connector: Connector | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.connector = connector or get_connector("sample")
        self.suite = AgentSuite.build(llm)

    def run(self, request: AnalysisRequest) -> DecisionReport:
        state, ctx = new_run(request, registry=self.registry, connector=self.connector)
        log.info("orchestrator.start", run_id=state.run_id, region=ctx.region.key,
                 engine="custom")

        # Linear evidence-gathering stages.
        for agent in self.suite.evidence_stages:
            agent.run(state, ctx)

        # Report ⟲ Critic loop.
        max_revisions = get_settings().critic_max_revisions
        self.suite.report.run(state, ctx)
        self.suite.critic.run(state, ctx)
        while (state.critic_review is not None and not state.critic_review.approved
               and state.revision_count < max_revisions):
            state.revision_count += 1
            log.info("orchestrator.revision", run_id=state.run_id,
                     revision=state.revision_count)
            self.suite.report.run(state, ctx)
            self.suite.critic.run(state, ctx)

        report = finalize(state)
        log.info("orchestrator.done", run_id=state.run_id, risk=report.risk_score,
                 approved=report.critic_review.approved, revisions=state.revision_count,
                 engine="custom")
        return report


def get_orchestrator(llm: LLMProvider | None = None,
                     registry: ModelRegistry | None = None,
                     connector: Connector | None = None) -> BaseOrchestrator:
    """Return the configured orchestration engine (``VECTIS_ORCHESTRATOR``).

    Defaults to the custom engine. Selecting ``langgraph`` requires the optional
    ``langgraph`` dependency (``pip install -e '.[langgraph]'``).
    """
    if get_settings().orchestrator == "langgraph":
        from vectis.agents.langgraph_engine import LangGraphOrchestrator

        return LangGraphOrchestrator(llm=llm, registry=registry, connector=connector)
    return Orchestrator(llm=llm, registry=registry, connector=connector)


def run_analysis(request: AnalysisRequest) -> DecisionReport:
    """Convenience entry point: run one analysis with the configured engine."""
    return get_orchestrator().run(request)
