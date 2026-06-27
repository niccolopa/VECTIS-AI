"""Report Agent.

Composes the :class:`DecisionReport` — VECTIS's deliverable. It assembles the
risk score, the explainable drivers, the supporting evidence, and recommended
actions, then narrates a concise summary (via the LLM, with a deterministic
fallback). Crucially, it emits an :class:`Evidence` item for every driver claim,
so the Critic can verify that nothing is asserted without support.

On a Critic-triggered revision it tightens the report by dropping any claim the
Critic flagged as unsupported.
"""

from __future__ import annotations

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import (
    AgentState,
    CellRisk,
    CriticReview,
    DecisionReport,
    Direction,
    Driver,
    Evidence,
    Priority,
    RecommendedAction,
    RegionPrediction,
    RiskBand,
)


class ReportAgent(Agent):
    name = "report"
    responsibility = (
        "Compose the explainable Decision Report — score, drivers, evidence, "
        "and recommended actions (what to do)."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:
        prediction = state.prediction
        if prediction is None:
            return StepResult(summary="Report skipped: no prediction available.")

        predictor = ctx.artifacts.get("predictor")
        metrics = predictor.card.metrics if predictor else {}
        band = RiskBand.from_score(prediction.aggregate_risk_score)

        drivers = self._report_drivers(prediction)
        evidence = self._evidence(state, prediction, drivers, metrics)
        confidence = self._confidence(metrics)
        actions = self._actions(band, drivers)
        summary = self._summary(state, prediction, band, drivers, confidence)

        # Apply Critic feedback from a prior round: drop flagged claims.
        flagged = self._flagged_claims(state.critic_review)
        if flagged:
            drivers = [d for d in drivers if d.name not in flagged]
            evidence = [e for e in evidence if e.statement not in flagged]

        report = DecisionReport(
            id=state.run_id,
            region=ctx.region.key,
            area_label=ctx.region.label,
            risk_score=prediction.aggregate_risk_score,
            confidence=confidence,
            summary=summary,
            drivers=drivers,
            evidence=evidence,
            recommended_actions=actions,
            cell_risks=[
                CellRisk(cell_id=c.cell_id, lat=c.lat, lon=c.lon, risk_score=c.risk_score)
                for c in prediction.cells
            ],
            critic_review=CriticReview(approved=False, notes="pending review"),
            model_card_ref=prediction.model_card_ref,
            trace=list(state.trace),
        )
        state.draft_report = report

        return StepResult(
            summary=f"Drafted decision report: risk {report.risk_score}/100 "
                    f"({band.value}), {len(drivers)} drivers, {len(evidence)} evidence items.",
            payload={"risk_band": band.value, "confidence": confidence},
            used_llm=state.data_summary.get("_summary_used_llm", False),
        )

    # --- composition helpers -------------------------------------------------
    @staticmethod
    def _report_drivers(prediction: RegionPrediction, k: int = 5) -> list[Driver]:
        """Headline drivers: risk-increasing first, then by magnitude."""
        ranked = sorted(
            prediction.top_drivers,
            key=lambda d: (d.direction != Direction.INCREASES, -abs(d.contribution)),
        )
        return ranked[:k]

    @staticmethod
    def _evidence(state: AgentState, prediction: RegionPrediction,
                  drivers: list[Driver], metrics: dict) -> list[Evidence]:
        evidence: list[Evidence] = [
            Evidence(
                source="model:shap",
                statement=f"{d.name} {d.direction.value} risk",
                metric=d.feature,
                value=round(d.contribution, 4),
            )
            for d in drivers
        ]
        for sig in state.signals:
            evidence.append(Evidence(source="data_analyst", statement=sig))
        if metrics.get("roc_auc") is not None:
            evidence.append(Evidence(
                source="model_card", metric="roc_auc", value=metrics["roc_auc"],
                statement=f"Model discrimination ROC-AUC={metrics['roc_auc']:.3f} "
                          f"on held-out cells.",
            ))
        return evidence

    @staticmethod
    def _confidence(metrics: dict) -> float:
        """Confidence blends model discrimination and calibration."""
        roc = metrics.get("roc_auc")
        brier = metrics.get("brier")
        if roc is None or brier is None:
            return 0.5
        return round(min(0.95, max(0.4, 0.5 * roc + 0.5 * (1 - brier))), 2)

    @staticmethod
    def _actions(band: RiskBand, drivers: list[Driver]) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []
        if band in (RiskBand.SEVERE, RiskBand.HIGH):
            actions += [
                RecommendedAction(
                    action="Increase monitoring of high-risk cells",
                    rationale="Aggregate risk is in the upper range; early detection "
                              "is the highest-leverage intervention.",
                    priority=Priority.HIGH),
                RecommendedAction(
                    action="Pre-position suppression resources near hotspots",
                    rationale="Concentrated high-probability cells warrant proximate "
                              "response capacity.",
                    priority=Priority.HIGH),
            ]
        elif band == RiskBand.MODERATE:
            actions.append(RecommendedAction(
                action="Maintain monitoring and schedule targeted inspections",
                rationale="Moderate risk with localized drivers; verify on the ground.",
                priority=Priority.MEDIUM))
        else:
            actions.append(RecommendedAction(
                action="Continue routine monitoring",
                rationale="Risk is low; no elevated intervention indicated.",
                priority=Priority.LOW))

        # Driver-specific guidance for the dominant risk-increasing factor.
        top_up = next((d for d in drivers if d.direction == Direction.INCREASES), None)
        if top_up is not None:
            actions.append(RecommendedAction(
                action=f"Investigate anomalies in '{top_up.name.lower()}'",
                rationale=f"{top_up.name} is the leading model-attributed driver of risk.",
                priority=Priority.MEDIUM))
        return actions

    def _summary(self, state: AgentState, prediction: RegionPrediction,
                 band: RiskBand, drivers: list[Driver], confidence: float) -> str:
        up = [d.name.lower() for d in drivers if d.direction == Direction.INCREASES][:3]
        driver_phrase = ", ".join(up) if up else "no single dominant driver"
        scenario_phrase = ""
        if state.scenarios:
            worst = max(state.scenarios, key=lambda s: s["risk_score"])
            scenario_phrase = (
                f" Under a '{worst['name'].replace('_', ' ')}' scenario, modeled risk "
                f"shifts to {worst['risk_score']}/100 ({worst['delta']:+.1f})."
            )
        fallback = (
            f"{prediction.region.title()} shows {band.value} wildfire risk "
            f"({prediction.aggregate_risk_score}/100, confidence {confidence:.0%}). "
            f"The risk is driven primarily by {driver_phrase}.{scenario_phrase}"
        )
        result = self.llm.narrate(
            instruction="Write a 2-3 sentence executive summary of this wildfire "
                        "risk assessment for a regional decision-maker.",
            context={
                "region": prediction.region,
                "risk_score": prediction.aggregate_risk_score,
                "risk_band": band.value,
                "confidence": confidence,
                "top_drivers": up,
                "scenarios": state.scenarios,
            },
            fallback=fallback,
        )
        state.data_summary["_summary_used_llm"] = result.used_llm
        return result.text

    @staticmethod
    def _flagged_claims(review: CriticReview | None) -> set[str]:
        if review is None:
            return set()
        return {issue.claim for issue in review.blockers}
