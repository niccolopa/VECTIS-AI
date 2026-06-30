"""Run one end-to-end analysis and print the Decision Report.

This is the fastest way to see VECTIS work: it seeds sample data and trains a
model if needed, runs the full multi-agent pipeline, and prints the resulting
Decision Intelligence Report — all offline, no API key required.

Run: ``python -m vectis.scripts.demo`` (or ``make demo``).
"""

from __future__ import annotations

import sys

from vectis.agents.orchestrator import Orchestrator
from vectis.core.schemas import AnalysisRequest, DecisionReport
from vectis.data.connectors import get_connector
from vectis.data.regions import get_region
from vectis.models.registry import ModelRegistry
from vectis.scripts.generate_sample import generate
from vectis.scripts.train import train_region


def _ensure_ready(region_key: str) -> None:
    """Make sure sample data and a trained model exist."""
    region = get_region(region_key)
    try:
        get_connector("sample").fetch(region)
    except Exception:
        generate(region)
    if not ModelRegistry().exists(region_key):
        train_region(region_key)


def _print_report(report: DecisionReport) -> None:
    line = "=" * 68
    print(f"\n{line}\nVECTIS DECISION INTELLIGENCE REPORT\n{line}")
    print(f"Area:        {report.area_label}")
    print(f"Risk Score:  {report.risk_score}/100  ({report.risk_band.value.upper()})")
    print(f"Confidence:  {report.confidence:.0%}")
    print(f"Model:       {report.model_card_ref}")
    print(f"\nSummary:\n  {report.summary}")
    print("\nMain Drivers:")
    for d in report.drivers:
        print(f"  - {d.name} ({d.direction.value}, SHAP {d.contribution:+.3f})")
    print("\nRecommended Actions:")
    for a in report.recommended_actions:
        print(f"  - [{a.priority.value}] {a.action}")
    review = report.critic_review
    print(f"\nCritic Review: {'APPROVED' if review.approved else 'NOT APPROVED'} "
          f"(revisions: {review.revision_count}, issues: {len(review.issues)})")
    for issue in review.issues:
        print(f"  - [{issue.severity}] {issue.problem}")
    print(f"\nEvidence items: {len(report.evidence)}  |  Agents run: {len(report.trace)}")
    print(line)


def main() -> None:
    region = sys.argv[1] if len(sys.argv) > 1 else "california"
    _ensure_ready(region)
    report = Orchestrator().run(AnalysisRequest(region=region))
    _print_report(report)


if __name__ == "__main__":
    main()
