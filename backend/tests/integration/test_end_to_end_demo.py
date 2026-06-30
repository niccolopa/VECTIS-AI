"""End-to-end test of the full V2 pipeline via the California demo script.

Exercises: weather alert → RealTimeUpdater → RegionTwin transition → Monte Carlo
(100k) → Bayesian update → LangGraph board → DecisionIntelligenceReport, and
asserts the rendered console output carries both the math and the brief structure.
"""

from __future__ import annotations

from io import StringIO

from vectis.agents.board.schemas import DecisionIntelligenceReport
from vectis.core.schemas import RiskBand
from vectis.scripts.demo_v2 import run_demo


def _run(color: bool = False):
    buf = StringIO()
    result = run_demo(iterations=100_000, seed=7, color=color, out=buf)
    return result, buf.getvalue()


# ── The pipeline computed real, updated math ─────────────────────────────────
def test_alert_raises_risk_and_shifts_beliefs():
    result, _ = _run()
    # The heatwave + drought drove risk up from the calm baseline...
    assert result.final.risk > result.baseline.risk
    assert result.final.band == RiskBand.SEVERE
    assert result.baseline.band in (RiskBand.LOW, RiskBand.MODERATE)
    # ...and the Bayesian update concentrated belief on the hotter/drier branch.
    assert result.final.scenario_priors["hotter_drier"] > result.baseline.scenario_priors["hotter_drier"]
    assert result.final.confidence > result.baseline.confidence


def test_report_is_well_formed_and_firewall_consistent():
    result, _ = _run()
    report = result.report
    assert isinstance(report, DecisionIntelligenceReport)
    assert report.region == "california"
    # Math Firewall: the report's numbers are exactly the engine's final numbers.
    assert report.analyst.risk_score == result.final.risk
    assert report.analyst.confidence_pct == round(result.final.confidence * 100, 1)
    assert len(report.scenarios) == 3
    assert report.debate.optimist_case and report.debate.pessimist_case
    assert report.red_team.blind_spots


# ── The console output is structured and complete ────────────────────────────
def test_console_output_has_all_sections():
    result, text = _run()
    for marker in (
        "VECTIS // DECISION INTELLIGENCE",
        "PHASE 1", "PHASE 3", "PHASE 5",
        "100,000",  # the Monte Carlo scenario count is surfaced
        "BASELINE RISK", "UPDATED RISK",
        "EXECUTIVE SUMMARY", "SCENARIO PROJECTIONS",
        "BLUE TEAM", "GOLD TEAM", "RED TEAM",
        "MATH FIREWALL ENFORCED",
    ):
        assert marker in text, f"missing section: {marker}"
    # The final risk score is actually printed.
    assert f"{result.final.risk:5.1f}/100" in text


def test_demo_is_deterministic():
    (r1, _), (r2, _) = _run(), _run()
    assert r1.final.risk == r2.final.risk
    assert r1.report.analyst.summary == r2.report.analyst.summary
