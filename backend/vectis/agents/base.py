"""Agent base class and shared run context.

Each agent is a small unit of reasoning that reads the shared
:class:`AgentState`, does its work, and writes results back — appending an
auditable :class:`AgentTrace`. The base class handles timing and tracing so
concrete agents implement only :meth:`_execute`.

Heavy, non-serializable intermediates (pandas frames, fitted artifacts) live on
the :class:`RunContext` "blackboard" rather than on the serializable
``AgentState``, keeping the state clean enough to persist and return over the API.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from vectis.agents.llm.base import LLMProvider
from vectis.agents.llm.factory import get_llm_provider
from vectis.core.logging import get_logger
from vectis.core.schemas import AgentState, AgentTrace
from vectis.data.connectors.base import Connector
from vectis.data.regions import Region
from vectis.models.registry import ModelRegistry

log = get_logger(__name__)


@dataclass
class RunContext:
    """Per-run working context shared across agents (not serialized)."""

    region: Region
    connector: Connector
    registry: ModelRegistry
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """What an agent reports about the step it just ran."""

    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    used_llm: bool = False


class Agent(ABC):
    """Base class for all VECTIS agents."""

    #: Stable identifier used in traces and logs.
    name: str = "agent"
    #: One-line statement of what this agent is accountable for (self-documenting;
    #: surfaced in docs and introspection).
    responsibility: str = ""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or get_llm_provider()

    @abstractmethod
    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        """Do the agent's work, mutating ``state``/``ctx``; return a summary."""
        raise NotImplementedError

    def run(self, state: AgentState, ctx: RunContext) -> AgentState:
        """Execute the agent with timing + tracing. Returns the mutated state."""
        start = time.perf_counter()
        result = self._execute(state, ctx)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        state.add_trace(
            AgentTrace(
                agent=self.name,
                summary=result.summary,
                duration_ms=duration_ms,
                used_llm=result.used_llm,
                payload=result.payload,
            )
        )
        log.info("agent.ran", agent=self.name, duration_ms=duration_ms,
                 used_llm=result.used_llm)
        return state
