"""ML Research Agent.

Owns the predictive layer — the "what could happen next" question. It loads the
selected model, predicts per-cell and aggregate risk, and attaches SHAP-based
driver attributions so every score is explainable. It also reports *which* model
was chosen and *why*, by surfacing the candidate comparison from the model card —
making the model-selection decision auditable rather than hidden.
"""

from __future__ import annotations

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import AgentState
from vectis.models.predictor import RiskPredictor


class MLResearchAgent(Agent):
    name = "ml_research"
    responsibility = (
        "Recommend and apply the predictive model; attribute the risk to its "
        "drivers (SHAP); justify model selection against the candidates."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        result = ctx.artifacts["pipeline"]
        predictor = RiskPredictor(ctx.region.key, registry=ctx.registry)
        prediction = predictor.predict(result)

        state.prediction = prediction
        ctx.artifacts["predictor"] = predictor

        card = predictor.card
        top = ", ".join(d.name for d in prediction.top_drivers[:3])
        # Compare the chosen model to the runners-up on ROC-AUC, for transparency.
        comparison = {
            name: {"roc_auc": m.get("roc_auc"), "brier": m.get("brier")}
            for name, m in card.candidates.items()
        }
        beaten = [n for n in card.candidates if n != card.model_name]
        summary = (
            f"Selected '{prediction.model_name}' (ROC-AUC "
            f"{card.metrics.get('roc_auc', float('nan')):.3f}) over {', '.join(beaten)} "
            f"by {card.notes or 'composite discrimination + calibration'}. "
            f"Region risk {prediction.aggregate_risk_score}/100 "
            f"(mean fire probability {prediction.mean_probability:.0%}); leading drivers: {top}."
        )
        return StepResult(
            summary=summary,
            payload={
                "model": prediction.model_name,
                "model_card_ref": prediction.model_card_ref,
                "aggregate_risk_score": prediction.aggregate_risk_score,
                "selection_rationale": card.notes,
                "candidates": comparison,
            },
        )
