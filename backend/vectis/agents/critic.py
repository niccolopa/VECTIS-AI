"""Critic Agent (mandatory).

The Critic is VECTIS's adversarial quality gate. It challenges the draft report:
every driver claim must be backed by evidence, the risk score and confidence
must be internally consistent, and the recommended actions must match the
severity. Findings are structured :class:`CriticIssue`s; any ``blocker`` marks
the report unapproved and triggers a bounded revision by the Report agent.

It is deliberately rule-based and deterministic: a validation gate must be
reliable and reproducible. (LLM-assisted critique is a documented roadmap item,
layered on top of — not replacing — these invariants.)
"""

from __future__ import annotations

from vectis.agents.base import Agent, RunContext, StepResult
from vectis.core.schemas import (
    AgentState,
    CriticIssue,
    CriticReview,
    DecisionReport,
    Priority,
    RiskBand,
)


class CriticAgent(Agent):
    name = "critic"
    responsibility = (
        "Challenge the draft report: enforce that every claim has evidence, the "
        "score/confidence are consistent, and actions match the risk."
    )

    def _execute(self, state: AgentState, ctx: RunContext) -> StepResult:  # noqa: ARG002
        report = state.draft_report
        if report is None:
            review = CriticReview(approved=False, revision_count=state.revision_count,
                                  notes="No draft report to review.")
            state.critic_review = review
            return StepResult(summary="Critic: no report to review.")

        issues = [*self._check_evidence(report), *self._check_consistency(report),
                  *self._check_actions(report)]
        blockers = [i for i in issues if i.severity == "blocker"]
        approved = not blockers

        review = CriticReview(
            approved=approved,
            revision_count=state.revision_count,
            issues=issues,
            notes=("Report substantiated; all driver claims have supporting evidence."
                   if approved else
                   f"{len(blockers)} blocking issue(s) require revision."),
        )
        state.critic_review = review
        # Stamp the verdict onto the report so the API surface reflects review state.
        report.critic_review = review

        summary = (f"Critic {'approved' if approved else 'rejected'} the report "
                   f"({len(issues)} issue(s), {len(blockers)} blocker(s)).")
        return StepResult(summary=summary,
                          payload={"approved": approved, "n_issues": len(issues)})

    # --- checks --------------------------------------------------------------
    @staticmethod
    def _check_evidence(report: DecisionReport) -> list[CriticIssue]:
        """Every driver must be referenced by at least one evidence item."""
        issues: list[CriticIssue] = []
        evidence_metrics = {e.metric for e in report.evidence if e.metric}
        evidence_text = " ".join(e.statement.lower() for e in report.evidence)
        for d in report.drivers:
            supported = d.feature in evidence_metrics or d.name.lower() in evidence_text
            if not supported:
                issues.append(CriticIssue(
                    severity="blocker",
                    claim=d.name,
                    problem=f"Driver '{d.name}' is asserted without supporting evidence.",
                ))
        if not report.drivers:
            issues.append(CriticIssue(
                severity="warning", claim="drivers",
                problem="Report lists no drivers; risk is unexplained.",
            ))
        return issues

    @staticmethod
    def _check_consistency(report: DecisionReport) -> list[CriticIssue]:
        issues: list[CriticIssue] = []
        if not 0 <= report.risk_score <= 100:
            issues.append(CriticIssue(severity="blocker", claim="risk_score",
                                      problem="Risk score outside [0, 100]."))
        if report.confidence >= 0.9 and report.risk_score >= 70 and len(report.evidence) < 3:
            issues.append(CriticIssue(
                severity="warning", claim="confidence",
                problem="High confidence on high risk with thin evidence (<3 items).",
            ))
        return issues

    @staticmethod
    def _check_actions(report: DecisionReport) -> list[CriticIssue]:
        issues: list[CriticIssue] = []
        if not report.recommended_actions:
            issues.append(CriticIssue(severity="blocker", claim="recommended_actions",
                                      problem="No recommended actions provided."))
            return issues
        band = report.risk_band
        has_high = any(a.priority == Priority.HIGH for a in report.recommended_actions)
        if band in (RiskBand.SEVERE, RiskBand.HIGH) and not has_high:
            issues.append(CriticIssue(
                severity="blocker", claim="recommended_actions",
                problem=f"{band.value.title()} risk but no high-priority action recommended.",
            ))
        return issues
