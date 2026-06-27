"""Agent node logic for the Simulation Analysis Board.

Each ``run_*`` function is one analyst: it assembles the authoritative numbers into
an LLM ``context``, writes a deterministic intelligence-grade ``fallback``, calls
the provider's :meth:`narrate`, and returns a typed schema object whose **numeric
fields are copied from the input** (never from the model). The deterministic mock
returns the fallback verbatim, so offline/CI output is itself a serious brief.

These functions are framework-agnostic (no LangGraph): ``team.py`` wraps them as
graph nodes, and the service's sequential fallback calls them directly — both paths
share this single source of logic, so they produce identical reports.
"""

from __future__ import annotations

from vectis.agents.board import prompts
from vectis.agents.board.schemas import (
    AnalystBrief,
    BoardInput,
    DebateRound,
    RedTeamCritique,
    ScenarioNarrative,
    ScenarioView,
)
from vectis.agents.llm.base import LLMProvider

# Operational consequence lines per scenario (deterministic narration scaffolding).
# ponytail: hand-authored impact phrasing; a real LLM enriches these via the prompt.
_SCENARIO_IMPACT: dict[str, str] = {
    "baseline": "routine seasonal readiness suffices, but vigilance must not lapse",
    "hotter_drier": (
        "fuel moisture collapses and coastal evacuation corridors and the "
        "wildland-urban interface come under sustained pressure"
    ),
    "extreme_wind": (
        "wind-driven spread outpaces initial attack and ignition can jump "
        "containment lines toward populated valleys"
    ),
}
_DEFAULT_IMPACT = "response posture and protection of the wildland-urban interface come under pressure"


def _pct(x: float) -> str:
    return f"{x:.0f}%"


def _dominant(inp: BoardInput) -> ScenarioView | None:
    return max(inp.scenarios, key=lambda s: s.probability, default=None)


def run_analyst(inp: BoardInput, llm: LLMProvider) -> AnalystBrief:
    """Executive summary. Figures copied from ``inp``; only the prose is narrated."""
    conf_pct = inp.confidence * 100.0
    residual = 100.0 - conf_pct
    dom = _dominant(inp)
    dom_clause = (
        f" The dominant signal is the '{dom.name}' trajectory at {_pct(dom.probability * 100)} "
        f"posterior weight." if dom else ""
    )
    fallback = (
        f"BLUF: {inp.region.title()} wildfire risk is assessed {inp.risk_band.value.upper()} at "
        f"{inp.risk_score:.0f}/100 with {_pct(conf_pct)} analytic confidence. Primary driver: "
        f"{inp.primary_driver}.{dom_clause} The figure is decision-grade but bounded by a "
        f"{_pct(residual)} residual; posture resources to the assessed band and hold reserve "
        f"against the tail."
    )
    result = llm.narrate(
        instruction=prompts.ANALYST_PROMPT,
        context=inp.model_dump(mode="json"),
        fallback=fallback,
    )
    return AnalystBrief(
        summary=result.text,
        risk_score=inp.risk_score,
        confidence_pct=round(conf_pct, 1),
        risk_band=inp.risk_band,
        primary_driver=inp.primary_driver,
    )


def run_scenarios(inp: BoardInput, llm: LLMProvider) -> list[ScenarioNarrative]:
    """One storyline per statistical scenario, at its fixed probability."""
    narratives: list[ScenarioNarrative] = []
    for sc in inp.scenarios:
        prob_pct = sc.probability * 100.0
        impact = _SCENARIO_IMPACT.get(sc.id, _DEFAULT_IMPACT)
        fallback = (
            f"At {_pct(prob_pct)} probability, the '{sc.name}' branch implies: {sc.description} "
            f"Operationally, sustained conditions of this branch mean {impact}."
        )
        result = llm.narrate(
            instruction=prompts.SCENARIO_PROMPT,
            context={"scenario": sc.model_dump(mode="json"), "region": inp.region},
            fallback=fallback,
        )
        narratives.append(
            ScenarioNarrative(
                scenario_id=sc.id,
                name=sc.name,
                probability_pct=round(prob_pct, 1),
                storyline=result.text,
            )
        )
    return narratives


def run_debate(inp: BoardInput, analyst: AnalystBrief, llm: LLMProvider) -> DebateRound:
    """Convenience: run both debate sub-agents and assemble the round."""
    return DebateRound(
        optimist_case=run_optimist(inp, analyst, llm),
        pessimist_case=run_pessimist(inp, analyst, llm),
    )


def run_optimist(inp: BoardInput, analyst: AnalystBrief, llm: LLMProvider) -> str:
    """Blue-team reading — more manageable than the headline, same numbers."""
    conf_pct = inp.confidence * 100.0
    fallback = (
        f"BLUE TEAM: The {_pct(conf_pct)} confidence reflects a model that has converged on a "
        f"clear driver, which makes the threat legible and therefore actionable. Pre-positioned "
        f"mitigation against {inp.primary_driver.lower()} can blunt the assessed {inp.risk_score:.0f}/100 "
        f"before it materializes; the lower-severity branches still hold non-trivial weight and "
        f"buy decision time. The assessment is a call to act early, not to assume the worst."
    )
    return llm.narrate(
        instruction=prompts.OPTIMIST_PROMPT,
        context={"input": inp.model_dump(mode="json"), "analyst": analyst.summary},
        fallback=fallback,
    ).text


def run_pessimist(inp: BoardInput, analyst: AnalystBrief, llm: LLMProvider) -> str:
    """Gold-team reading — more dangerous than the headline, same numbers."""
    residual = 100.0 - inp.confidence * 100.0
    fallback = (
        f"GOLD TEAM: The headline understates exposure. A {_pct(residual)} confidence residual is "
        f"unmodeled tail risk, and the worst-credible branches compound rather than average. If "
        f"{inp.primary_driver.lower()} persists, escalation is non-linear: containment that holds at "
        f"{inp.risk_score:.0f}/100 fails fast once a threshold is crossed. Plan to the tail, not the mean."
    )
    return llm.narrate(
        instruction=prompts.PESSIMIST_PROMPT,
        context={"input": inp.model_dump(mode="json"), "analyst": analyst.summary},
        fallback=fallback,
    ).text


def run_critic(
    inp: BoardInput, analyst: AnalystBrief, debate: DebateRound, llm: LLMProvider
) -> RedTeamCritique:
    """Red-team attack: the blind spots the math cannot see. Residual is copied."""
    residual = round(100.0 - inp.confidence * 100.0, 1)
    blind_spots = [
        f"Confidence is {_pct(inp.confidence * 100)}; the {_pct(residual)} residual is unmodeled "
        "tail risk, not certified safety.",
        "Anthropogenic ignition — arson, powerline faults, discarded ordnance — is absent from the "
        "hazard model; the score reflects environmental drivers only.",
        "Sub-grid wind gusts and fuel-moisture micro-variation are smoothed by regional "
        "aggregation; local flashpoints can exceed the area assessment.",
        "Cascading infrastructure failure (power, water, comms) under fire load is out of model scope.",
    ]
    dom = _dominant(inp)
    if dom is not None and dom.id == "baseline":
        blind_spots.append(
            "The dominant branch is 'baseline' — beware complacency; the model rewards the status quo "
            "until an indicator breaks."
        )
    fallback = (
        f"RED TEAM: Do not mistake {_pct(inp.confidence * 100)} confidence for coverage. The model is "
        f"blind to human ignition and to sub-grid wind — precisely the vectors that turn a "
        f"{inp.risk_band.value} assessment into a mass-casualty event. The {_pct(residual)} residual is "
        f"where the surprise lives; treat the single largest blind spot — unmodeled arson — as an active "
        f"intelligence gap, not an accepted risk."
    )
    result = llm.narrate(
        instruction=prompts.CRITIC_PROMPT,
        context={
            "input": inp.model_dump(mode="json"),
            "analyst": analyst.summary,
            "debate": debate.model_dump(mode="json"),
        },
        fallback=fallback,
    )
    return RedTeamCritique(
        challenge=result.text,
        blind_spots=blind_spots,
        residual_uncertainty_pct=residual,
    )
