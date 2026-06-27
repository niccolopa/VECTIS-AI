"""LangGraph orchestration engine (optional, selectable backend).

Expresses the exact same flow as the custom engine — but as a LangGraph
``StateGraph`` — reusing the *same* agents and run setup via
:mod:`vectis.agents.runtime`. Choosing this engine (``VECTIS_ORCHESTRATOR=langgraph``)
buys the LangGraph runtime (typed graph, conditional edges, and a path to
checkpointing/streaming) without changing any agent.

    START → discovery → analyst → ml_research → simulation → report → critic
                                                                   │
                                              (blocker & revisions left) ──► report
                                                                   │
                                                                  END

Why a separate module: LangGraph is an optional dependency, imported lazily by
``get_orchestrator`` so the default install stays lean and offline.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from vectis.agents.base import Agent, RunContext
from vectis.agents.llm.base import LLMProvider
from vectis.agents.runtime import AgentSuite, finalize, new_run
from vectis.core.config import get_settings
from vectis.core.logging import get_logger
from vectis.core.schemas import AgentState, AnalysisRequest, DecisionReport
from vectis.data.connectors import get_connector
from vectis.data.connectors.base import Connector
from vectis.models.registry import ModelRegistry

log = get_logger(__name__)


class _GraphState(TypedDict):
    """Graph channels. Agents mutate ``state``/``ctx`` in place; nodes return {}."""

    state: AgentState
    ctx: RunContext


class LangGraphOrchestrator:
    """Runs the multi-agent pipeline via a compiled LangGraph state machine."""

    def __init__(self, llm: LLMProvider | None = None,
                 registry: ModelRegistry | None = None,
                 connector: Connector | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.connector = connector or get_connector("sample")
        self.suite = AgentSuite.build(llm)
        self._app = self._build_graph()

    def _build_graph(self) -> Any:
        suite = self.suite
        max_revisions = get_settings().critic_max_revisions

        def node(agent: Agent) -> Callable[[_GraphState], dict]:
            def _run(gs: _GraphState) -> dict:
                agent.run(gs["state"], gs["ctx"])
                return {}

            return _run

        def route_after_critic(gs: _GraphState) -> str:
            """Loop back to Report on a Critic blocker, within the revision bound."""
            state = gs["state"]
            review = state.critic_review
            if review is not None and not review.approved and state.revision_count < max_revisions:
                state.revision_count += 1
                log.info("orchestrator.revision", run_id=state.run_id,
                         revision=state.revision_count, engine="langgraph")
                return "report"
            return END

        graph = StateGraph(_GraphState)
        graph.add_node("discovery", node(suite.discovery))
        graph.add_node("analyst", node(suite.analyst))
        graph.add_node("ml_research", node(suite.ml_research))
        graph.add_node("simulation", node(suite.simulation))
        graph.add_node("report", node(suite.report))
        graph.add_node("critic", node(suite.critic))

        graph.add_edge(START, "discovery")
        graph.add_edge("discovery", "analyst")
        graph.add_edge("analyst", "ml_research")
        graph.add_edge("ml_research", "simulation")
        graph.add_edge("simulation", "report")
        graph.add_edge("report", "critic")
        graph.add_conditional_edges("critic", route_after_critic,
                                    {"report": "report", END: END})
        return graph.compile()

    def run(self, request: AnalysisRequest) -> DecisionReport:
        state, ctx = new_run(request, registry=self.registry, connector=self.connector)
        log.info("orchestrator.start", run_id=state.run_id, region=ctx.region.key,
                 engine="langgraph")

        # recursion_limit guards against pathological loops; the Critic bound makes
        # the real ceiling small (stages + 2*revisions).
        self._app.invoke({"state": state, "ctx": ctx},
                         config={"recursion_limit": 50})

        report = finalize(state)
        log.info("orchestrator.done", run_id=state.run_id, risk=report.risk_score,
                 approved=report.critic_review.approved, revisions=state.revision_count,
                 engine="langgraph")
        return report
