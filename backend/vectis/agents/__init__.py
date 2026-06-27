"""Multi-agent decision-intelligence system.

A typed orchestrator threads an :class:`~vectis.core.schemas.AgentState` through an
explicit DAG of agents:

    Discovery → Analyst → ML Research → Simulation → Report ⟲ Critic

The Critic is mandatory: it challenges unsupported claims and can send the report
back for a bounded number of revisions.

Two interchangeable engines implement :class:`~vectis.agents.runtime.BaseOrchestrator`
over the *same* agents — a default ``custom`` engine (transparent, deterministic,
dependency-light) and an optional ``langgraph`` engine — selected by
``VECTIS_ORCHESTRATOR`` via :func:`get_orchestrator`.
"""

from vectis.agents.orchestrator import Orchestrator, get_orchestrator, run_analysis
from vectis.agents.runtime import AgentSuite, BaseOrchestrator

__all__ = [
    "Orchestrator",
    "get_orchestrator",
    "run_analysis",
    "AgentSuite",
    "BaseOrchestrator",
]
