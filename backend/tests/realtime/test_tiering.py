"""Session 33 — the tiering engine: shape-aware promotion under hard budgets."""

from __future__ import annotations

from vectis.realtime.screening.base import ScreeningScore
from vectis.realtime.tiering import (
    MAX_MEASURED_UNDERESTIMATE,
    T1_SCORE_CUTOFF,
    TRANSITION_BAND,
    TierManager,
    headline_scores,
    total_variation,
)


# ── Step 1: T0 → T1 promotion — three auditable gates, not one naive cutoff ────────────
def test_saturated_tail_promotes_on_score_alone() -> None:
    # Session 32 measured the screen accurate (gap ≤ 3.57) at/above the cutoff, and the
    # bias is one-sided low — a 92 can only really be ≥ 92, so the score alone suffices.
    decision = TierManager().evaluate("cell", 92.0)
    assert decision is not None
    assert decision.reason == "score_threshold"
    assert decision.priority == 92.0  # no band correction outside the transition band


def test_quiet_low_risk_cell_stays_t0() -> None:
    assert TierManager().evaluate("cell", 2.0) is None


def test_belief_shift_promotes_regardless_of_score() -> None:
    # A big posterior swing means something real changed even if the screen reads low.
    decision = TierManager().evaluate("cell", 2.0, belief_shift=0.6)
    assert decision is not None
    assert decision.reason == "belief_shift"
    assert decision.priority == 60.0  # shift ranked on its own 0–100 scale


def test_mid_band_cell_needs_an_upward_trend_to_promote() -> None:
    mgr = TierManager()
    # First sighting: mid-band but no trend history → stays T0 this cycle.
    assert mgr.consider({"cell": 40.0}) == []
    # Static next cycle: still no promotion — mid-band alone is not enough.
    assert mgr.consider({"cell": 40.0}) == []
    # Trending up inside the band: promote, because this is exactly where Session 32
    # measured the screen under-reading by up to 13.23 points.
    [decision] = mgr.consider({"cell": 44.0})
    assert decision.reason == "transition_band_trending_up"
    # It competes bias-corrected: ranked as the risk it may really be.
    assert decision.priority == 44.0 + MAX_MEASURED_UNDERESTIMATE


def test_mid_band_trend_below_epsilon_is_jitter_not_a_trend() -> None:
    mgr = TierManager(trend_epsilon=0.5)
    mgr.consider({"cell": 40.0})
    assert mgr.consider({"cell": 40.3}) == []  # within jitter, no promotion


def test_trending_up_outside_the_band_does_not_promote() -> None:
    # The trend gate exists only where the screen is untrustworthy; a rising 1→3 score
    # is still confidently low-risk (measured gap ~1 pt in the low tail).
    mgr = TierManager()
    mgr.consider({"cell": 1.0})
    assert mgr.consider({"cell": 3.0}) == []


def test_band_bounds_meet_the_score_cutoff() -> None:
    # The gates must cover the score axis with no dead zone: the band's upper edge is the
    # unconditional cutoff, so a cell is either tail-promoted, band-gated, or honestly low.
    assert TRANSITION_BAND[1] == T1_SCORE_CUTOFF
    assert TRANSITION_BAND[0] < TRANSITION_BAND[1]


def test_every_promotion_carries_its_audit_trail() -> None:
    mgr = TierManager()
    decisions = mgr.consider({"hot": 95.0, "shifted": 10.0}, belief_shifts={"shifted": 0.9})
    by_cell = {d.cell_id: d for d in decisions}
    assert by_cell["hot"].reason == "score_threshold"
    assert by_cell["shifted"].reason == "belief_shift"
    # The decision records the evidence it was made on, not just the verdict.
    assert by_cell["shifted"].score == 10.0
    assert by_cell["shifted"].belief_shift == 0.9


# ── helpers ─────────────────────────────────────────────────────────────────────────────
def test_total_variation_matches_the_session_22_concept() -> None:
    assert total_variation({"a": 1.0}, {"a": 1.0}) == 0.0
    assert total_variation({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}) == 1.0
    # Keys missing from one belief count as zero mass, not a crash.
    assert total_variation({"a": 1.0}, {"b": 1.0}) == 1.0


def test_headline_scores_collapse_the_sweep_by_worst_hazard() -> None:
    sweep = {
        "cell": {
            "wildfire": ScreeningScore("wildfire", 40.0),
            "flood": ScreeningScore("flood", 70.0),
        },
        "unscored": {},
    }
    scores = headline_scores(sweep)
    assert scores == {"cell": 70.0}  # ranked by the worst hazard; unscored cells absent
