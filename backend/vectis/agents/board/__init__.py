"""The Simulation Analysis Board — LLM intelligence analysts over V2 output.

This sub-package brings the V1 "LLM narrates, never decides" discipline to the V2
simulation layer. A team of agents *reads* a Digital Twin's :class:`RiskState`
(Sessions 8–10) and produces a structured :class:`DecisionIntelligenceReport`:

    Analyst → Scenario Narrator → Debate (Optimist · Pessimist) → Red-Team Critic

**The Math Firewall (non-negotiable):** every number originates from the
deterministic simulation engine. The agents are *commentators, not calculators* —
they may interpret, contextualize, and challenge the figures, but never recompute
or contradict them. Numeric fields in the report are **copied from the engine
output in code**; the LLM only writes prose, so a hallucinated figure in narration
can never overwrite an authoritative one.

Kept apart from the V1 ``agents/`` modules (the reactive ML/SHAP pipeline): this is
the V2 *probabilistic* analysis board, wired to the Digital Twin, not the ML model.
The graph is built with LangGraph when available, with a deterministic sequential
fallback so the board runs offline on a lean install.
"""
