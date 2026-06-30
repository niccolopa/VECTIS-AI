"""Unit tests for the domain contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vectis.core.schemas import (
    CriticReview,
    DecisionReport,
    Direction,
    Driver,
    RiskBand,
)


@pytest.mark.parametrize(
    "score,band",
    [(10, RiskBand.LOW), (30, RiskBand.MODERATE), (60, RiskBand.HIGH), (90, RiskBand.SEVERE)],
)
def test_risk_band_from_score(score: float, band: RiskBand) -> None:
    assert RiskBand.from_score(score) == band


def test_driver_from_shap_direction() -> None:
    up = Driver.from_shap("drought_index", 0.5, 0.3)
    down = Driver.from_shap("humidity_pct", 60.0, -0.2)
    assert up.direction == Direction.INCREASES
    assert down.direction == Direction.DECREASES


def test_decision_report_computes_band() -> None:
    report = DecisionReport(
        id="abc", region="california", area_label="California, USA",
        risk_score=80, confidence=0.8, summary="x",
        critic_review=CriticReview(approved=True), model_card_ref="ref",
    )
    assert report.risk_band == RiskBand.SEVERE


def test_decision_report_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        DecisionReport(
            id="abc", region="california", area_label="L", risk_score=150,
            confidence=0.8, summary="x",
            critic_review=CriticReview(approved=True), model_card_ref="ref",
        )


def test_critic_review_blockers_property() -> None:
    review = CriticReview(
        approved=False,
        issues=[
            {"severity": "blocker", "claim": "a", "problem": "p"},
            {"severity": "warning", "claim": "b", "problem": "q"},
        ],
    )
    assert len(review.blockers) == 1
