"""Service entry point for the Simulation Analysis Board.

:class:`SimulationBoardService` is the modular trigger: hand it a ``RegionTwin``
(or a :class:`BoardInput` directly, decoupled from the real-time stream) and it
returns a compiled :class:`DecisionIntelligenceReport`.

It prefers the LangGraph state machine (:mod:`team`); if LangGraph isn't installed
it runs the same :mod:`nodes` sequentially. Both paths share node logic, so the
report is identical — the graph is an execution choice, not a different analysis.
"""

from __future__ import annotations

from vectis.agents.board import nodes
from vectis.agents.board.schemas import (
    BoardInput,
    DecisionIntelligenceReport,
    ScenarioView,
)
from vectis.agents.llm.base import LLMProvider
from vectis.agents.llm.factory import get_llm_provider
from vectis.core.logging import get_logger
from vectis.digital_twin.entities.region import RegionTwin

log = get_logger(__name__)

# Human driver label per dominant scenario (read-only mapping, firewall-safe).
_DRIVER_LABELS: dict[str, str] = {
    "baseline": "Prevailing seasonal conditions",
    "hotter_drier": "Temperature & rainfall anomaly",
    "extreme_wind": "Wind-driven ignition spread",
}


def board_input_from_twin(twin: RegionTwin) -> BoardInput:
    """Assemble the firewall's source-of-truth numbers from a region twin."""
    risk = twin.computed_risk_state
    scenarios = [
        ScenarioView(
            id=s.id, name=s.name, description=s.description,
            probability=risk.scenario_priors.get(s.id, s.prior),
        )
        for s in twin.scenarios.scenarios
    ]
    dominant = max(scenarios, key=lambda s: s.probability, default=None)
    driver = (
        _DRIVER_LABELS.get(dominant.id, dominant.name) if dominant is not None else "Undetermined"
    )
    return BoardInput(
        region=risk.region,
        risk_score=risk.risk,
        confidence=risk.confidence,
        risk_band=risk.band,
        primary_driver=driver,
        scenarios=scenarios,
    )


class SimulationBoardService:
    """Runs the analysis board and compiles the intelligence report."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm or get_llm_provider()

    def analyze_twin(self, twin: RegionTwin) -> DecisionIntelligenceReport:
        """Generate a report for a Digital Twin's current risk state."""
        return self.analyze(board_input_from_twin(twin))

    def analyze(self, inp: BoardInput) -> DecisionIntelligenceReport:
        """Generate a report from the engine numbers (stream-independent)."""
        state = self._run(inp)
        report = DecisionIntelligenceReport(
            region=inp.region,
            bottom_line=self._bottom_line(inp),
            source=inp,
            analyst=state["analyst"],
            scenarios=state["scenarios"],
            debate=state["debate"],
            red_team=state["red_team"],
        )
        log.info(
            "board.report", region=inp.region, risk=round(inp.risk_score, 1),
            confidence=round(inp.confidence, 3), report_id=report.report_id,
        )
        return report

    # ── execution: LangGraph, or sequential fallback ─────────────────────────
    def _run(self, inp: BoardInput) -> dict:
        try:
            from vectis.agents.board.team import build_board_graph
        except ImportError:  # LangGraph not installed — run the same nodes in order.
            log.info("board.sequential_fallback")
            return self._run_sequential(inp)
        result = build_board_graph(self._llm).invoke({"inp": inp})
        return dict(result)

    def _run_sequential(self, inp: BoardInput) -> dict:
        analyst = nodes.run_analyst(inp, self._llm)
        scenarios = nodes.run_scenarios(inp, self._llm)
        debate = nodes.run_debate(inp, analyst, self._llm)
        red_team = nodes.run_critic(inp, analyst, debate, self._llm)
        return {"analyst": analyst, "scenarios": scenarios, "debate": debate, "red_team": red_team}

    def _bottom_line(self, inp: BoardInput) -> str:
        residual = 100.0 - inp.confidence * 100.0
        return (
            f"{inp.region.title()} assessed {inp.risk_band.value.upper()} — {inp.risk_score:.0f}/100, "
            f"confidence {inp.confidence * 100:.0f}% ({residual:.0f}% residual). Primary driver: "
            f"{inp.primary_driver}. Posture to the assessed band; hold reserve against the tail."
        )
