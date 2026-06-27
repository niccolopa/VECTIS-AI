"""The Simulation Analysis Board as a LangGraph state machine.

    START → analyst → scenarios → optimist → pessimist → critic → END

The ``BoardState`` is the channel dict passed between nodes; each node reads the
prior channels and writes its own output. The two debate sub-agents are distinct
nodes (Optimist then Pessimist) that accumulate into a single :class:`DebateRound`,
so the graph literally shows Analyst → Scenario → Debate → Critic.

LangGraph is an optional dependency (imported here at module top); the service
falls back to a sequential runner over the same :mod:`nodes` functions when it is
absent, producing an identical report.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from vectis.agents.board import nodes
from vectis.agents.board.schemas import (
    AnalystBrief,
    BoardInput,
    DebateRound,
    RedTeamCritique,
    ScenarioNarrative,
)
from vectis.agents.llm.base import LLMProvider


class BoardState(TypedDict, total=False):
    """Channels passed between board nodes (each node fills its own)."""

    inp: BoardInput
    analyst: AnalystBrief
    scenarios: list[ScenarioNarrative]
    debate: DebateRound
    red_team: RedTeamCritique


def build_board_graph(llm: LLMProvider) -> Any:
    """Compile the board's LangGraph state machine bound to ``llm``."""

    def analyst_node(s: BoardState) -> dict:
        return {"analyst": nodes.run_analyst(s["inp"], llm)}

    def scenarios_node(s: BoardState) -> dict:
        return {"scenarios": nodes.run_scenarios(s["inp"], llm)}

    def optimist_node(s: BoardState) -> dict:
        case = nodes.run_optimist(s["inp"], s["analyst"], llm)
        return {"debate": DebateRound(optimist_case=case, pessimist_case="")}

    def pessimist_node(s: BoardState) -> dict:
        case = nodes.run_pessimist(s["inp"], s["analyst"], llm)
        return {"debate": DebateRound(optimist_case=s["debate"].optimist_case, pessimist_case=case)}

    def critic_node(s: BoardState) -> dict:
        return {"red_team": nodes.run_critic(s["inp"], s["analyst"], s["debate"], llm)}

    graph = StateGraph(BoardState)
    graph.add_node("analyst", analyst_node)
    graph.add_node("scenarios", scenarios_node)
    graph.add_node("optimist", optimist_node)
    graph.add_node("pessimist", pessimist_node)
    graph.add_node("critic", critic_node)

    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", "scenarios")
    graph.add_edge("scenarios", "optimist")
    graph.add_edge("optimist", "pessimist")
    graph.add_edge("pessimist", "critic")
    graph.add_edge("critic", END)
    return graph.compile()
