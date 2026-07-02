"""``TierManager`` — the bounded promotion gate between cheap screening and deep analysis.

Session 32 gave every active cell a near-free screening score (Tier 0). This module is the
mechanism that makes planetary scale computationally bounded: it decides which few of those
cells get **promoted** to the expensive tiers —

- **T0** — screened only (:class:`~vectis.realtime.screening.sweep.GlobalScreeningSweep`).
- **T1** — the full Monte Carlo + Bayesian forecast (the Session-22 slow path).
- **T2** — the decision-board / LLM narration pass (the most expensive stage of all).

Shape-aware promotion (the Session 32 finding this module exists to honour)
---------------------------------------------------------------------------
The measured screening-vs-full-engine gap is **biased low, not random** (see the gap table
in ``tests/realtime/test_screening.py``): within ~1 pt where risk saturates near 0 or 100,
but under-estimating by up to **13.23 pts** in the mid-risk transition band, because the
screen evaluates only the baseline scenario and omits the upward ``hotter_drier`` /
``extreme_wind`` scenarios the engine mixes in. A single naive cutoff would therefore
systematically ignore exactly the cells the screen is most wrong about. So promotion is
three-gated, and every decision carries its :class:`PromotionReason` so an operator can
audit *why* a cell got expensive treatment:

- ``score_threshold`` — screen ≥ :data:`T1_SCORE_CUTOFF` (the saturated high tail, where
  Session 32 measured the screen accurate to ≤3.57 pts *and* the bias is one-sided low, so
  the true risk can only be higher — promote unconditionally).
- ``belief_shift`` — the cell's scenario posterior moved by ≥ the total-variation threshold
  since the last cycle (the Session-22 ``belief_shift`` signal): something real changed,
  regardless of the absolute score.
- ``transition_band_trending_up`` — the cell sits inside :data:`TRANSITION_BAND` **and**
  its screen score is rising. That band is precisely where the screen quietly under-reads,
  so "mid-risk and getting worse" promotes even though the raw score alone would not.

Where the band bounds come from (measured, not guessed): the Session-32 gap table
(screen → under-estimate) reads 0.76→1.09, 6.45→6.88, 38.34→13.23, 84.88→3.57, 98.06→0.42.
Every point whose gap exceeded the 5-pt materiality threshold (the same threshold the
Session-22 board gate uses for "the risk moved materially") had a screen score between
6.45 and 38.34; :data:`TRANSITION_BAND` = **[5, 85)** brackets that region with margin and
meets :data:`T1_SCORE_CUTOFF` at 85, above which the measured gap (≤3.57) is immaterial.

Pure arithmetic and bookkeeping — no LLM, no simulation import. The Math Firewall holds.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from vectis.core.logging import get_logger
from vectis.realtime.events.base import CellId
from vectis.realtime.screening.base import ScreeningScore

logger = get_logger(__name__)

#: Largest measured screening under-estimate (Session 32 gap table: screen 38.34 vs
#: engine 51.58). Used to bias-correct a transition-band cell's queue priority, so a
#: mid-band cell competes as the risk it *may really be*, not the number the screen read.
MAX_MEASURED_UNDERESTIMATE = 13.23

#: Screening-score band [low, high) where Session 32 measured the screen materially wrong
#: (gap > the 5-pt materiality threshold — derivation in the module docstring).
TRANSITION_BAND: tuple[float, float] = (5.0, 85.0)

#: High-confidence cutoff: at/above this screen score the Session-32 gap is ≤3.57 pts and
#: one-sided low, so the cell is genuinely high-risk — promote on the score alone.
T1_SCORE_CUTOFF = 85.0

PromotionReason = Literal["score_threshold", "belief_shift", "transition_band_trending_up"]


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """One auditable T0→T1 promotion: which cell, why, and on what evidence."""

    cell_id: CellId
    reason: PromotionReason
    score: float  #: raw screening score (0–100) at decision time
    belief_shift: float  #: total-variation posterior move since last cycle (0–1)
    priority: float  #: queue rank — bias-corrected score / shift on the 0–100+ scale


def total_variation(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """TV distance between two categorical beliefs: ``½·Σ|a−b|`` over the union of keys.

    The Session-22 ``belief_shift`` concept (``digital_twin.entities.region``), restated
    over the plain posterior dicts the :class:`ContinuousPipeline` carries per cell.
    """
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in a.keys() | b.keys())


def headline_scores(
    sweep: Mapping[CellId, Mapping[str, ScreeningScore]],
) -> dict[CellId, float]:
    """Collapse a :class:`GlobalScreeningSweep` result to one headline score per cell.

    The tier decision is per *cell* (one budget, one queue), so multi-hazard cells rank by
    their worst hazard. Cells no hazard could score are absent, exactly as the sweep left them.
    """
    return {
        cell: max(score.value for score in hazards.values())
        for cell, hazards in sweep.items()
        if hazards
    }


class TierManager:
    """Decide which active cells get promoted from screened-only (T0) to deep analysis.

    Consumes the Session-32 sweep's headline scores plus each cell's current belief-shift
    signal, and applies the three shape-aware gates documented in the module docstring.
    Every promotion is returned as an auditable :class:`PromotionDecision`.

    ponytail: thresholds are hand-set from the Session-32 measurements; recalibrate them
    when Session 34 fits the model against real labels.
    """

    def __init__(
        self,
        *,
        t1_score_cutoff: float = T1_SCORE_CUTOFF,
        transition_band: tuple[float, float] = TRANSITION_BAND,
        belief_shift_threshold: float = 0.2,
        trend_epsilon: float = 0.5,
    ) -> None:
        self._t1_score_cutoff = t1_score_cutoff
        self._band_low, self._band_high = transition_band
        self._belief_shift_threshold = belief_shift_threshold
        #: minimum score rise vs the previous cycle to count as "trending up" — damps
        #: float jitter from re-screening near-identical state.
        self._trend_epsilon = trend_epsilon

        #: previous cycle's screen score per cell — the memory the trend gate reads.
        self._last_score: dict[CellId, float] = {}

    # ── T0 → T1 ───────────────────────────────────────────────────────────────────
    def evaluate(
        self, cell_id: CellId, score: float, belief_shift: float = 0.0
    ) -> PromotionDecision | None:
        """Apply the three promotion gates to one cell; ``None`` means it stays T0.

        Pure read — trend memory is updated by :meth:`consider`, which sees the whole
        cycle's sweep at once.
        """
        in_band = self._band_low <= score < self._band_high
        previous = self._last_score.get(cell_id)

        reason: PromotionReason
        if score >= self._t1_score_cutoff:
            reason = "score_threshold"
        elif belief_shift >= self._belief_shift_threshold:
            reason = "belief_shift"
        elif in_band and previous is not None and score > previous + self._trend_epsilon:
            reason = "transition_band_trending_up"
        else:
            return None

        # Rank by what the cell *may really be*: inside the band the screen under-reads by
        # up to the measured 13.23 pts, so band cells compete bias-corrected; a big belief
        # shift ranks on its own 0–100 scale.
        corrected = score + (MAX_MEASURED_UNDERESTIMATE if in_band else 0.0)
        priority = max(corrected, belief_shift * 100.0)
        return PromotionDecision(cell_id, reason, score, belief_shift, priority)

    def consider(
        self,
        scores: Mapping[CellId, float],
        belief_shifts: Mapping[CellId, float] | None = None,
    ) -> list[PromotionDecision]:
        """Evaluate one sweep's worth of cells; return every promotion decided this cycle.

        Also records each cell's score as the next cycle's trend baseline — a mid-band
        cell first seen this cycle has no trend yet, so it can only promote next cycle
        (or immediately, via the score/belief gates).
        """
        shifts = belief_shifts or {}
        decisions: list[PromotionDecision] = []
        for cell_id, score in scores.items():
            decision = self.evaluate(cell_id, score, shifts.get(cell_id, 0.0))
            if decision is not None:
                decisions.append(decision)
                logger.debug(
                    "[TIER] promote %s -> T1 (%s: score=%.1f shift=%.3f prio=%.1f)",
                    cell_id, decision.reason, score, decision.belief_shift, decision.priority,
                )
            self._last_score[cell_id] = score
        return decisions


def demo() -> None:
    """Self-check: each gate fires for its own reason and the quiet cells stay T0."""
    mgr = TierManager()
    # Cycle 1: the saturated-tail cell promotes on score; the mid-band cell has no trend yet.
    first = {d.cell_id: d for d in mgr.consider({"tail": 92.0, "mid": 40.0, "cold": 2.0})}
    assert first["tail"].reason == "score_threshold"
    assert "mid" not in first and "cold" not in first, first
    # Cycle 2: the mid-band cell trends up → promotes despite a sub-cutoff raw score, with
    # a bias-corrected priority; a quiet cell with a big posterior swing promotes too.
    second = {
        d.cell_id: d
        for d in mgr.consider({"mid": 45.0, "cold": 2.0}, belief_shifts={"cold": 0.6})
    }
    assert second["mid"].reason == "transition_band_trending_up"
    assert second["mid"].priority == 45.0 + MAX_MEASURED_UNDERESTIMATE
    assert second["cold"].reason == "belief_shift"
    print("OK", {c: d.reason for c, d in second.items()})


if __name__ == "__main__":
    demo()
