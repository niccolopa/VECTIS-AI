"""Tiered promotion — the bounded gate from cheap screening to deep analysis (Session 33).

:class:`TierManager` consumes the Session-32 screening sweep plus each cell's belief-shift
signal and decides, under hard per-cycle budgets, which few cells get the expensive
Monte Carlo + Bayesian pass (T1) and which of those get a decision-board narration (T2).
"""

from __future__ import annotations

from vectis.realtime.tiering.manager import (
    MAX_MEASURED_UNDERESTIMATE,
    T1_SCORE_CUTOFF,
    TRANSITION_BAND,
    BoardSlot,
    PromotionDecision,
    PromotionReason,
    TierManager,
    headline_scores,
    total_variation,
)

__all__ = [
    "MAX_MEASURED_UNDERESTIMATE",
    "T1_SCORE_CUTOFF",
    "TRANSITION_BAND",
    "BoardSlot",
    "PromotionDecision",
    "PromotionReason",
    "TierManager",
    "headline_scores",
    "total_variation",
]
