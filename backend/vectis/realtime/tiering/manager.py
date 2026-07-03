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

import os
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from vectis.core.logging import get_logger
from vectis.core.schemas import RiskBand
from vectis.realtime.events.base import CellId
from vectis.realtime.pipeline import DEFAULT_RISK_CHANGE_THRESHOLD, risk_moved
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

PromotionReason = Literal[
    "score_threshold", "belief_shift", "transition_band_trending_up", "watchlist_refresh"
]


@dataclass(frozen=True, slots=True)
class BoardSlot:
    """One granted T2 slot: convene the decision board for this cell this cycle."""

    cell_id: CellId
    risk: float  #: current headline risk (0–100) from the fresh T1 forecast
    change: float  #: magnitude of the move since the last report (== risk if never reported)
    watchlisted: bool = False  #: pinned by an operator — won its slot on priority (audit)


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


@dataclass(frozen=True, slots=True)
class TieringMetrics:
    """One cycle's back-pressure numbers — what an operator (or autoscaler) watches.

    ``waited_over_one_cycle`` counts cells currently queued (T1 or T2) that have been
    passed over by more than one budget round: sustained non-zero values mean demand is
    outrunning the per-cycle budgets and the queues are aging, not just briefly spiking.
    """

    cycle: int
    hot_set_size: int  #: cells screened this cycle (the sweep's active set)
    t1_promoted: int  #: new T0→T1 promotions decided this cycle
    t1_executed: int  #: deep-analysis slots granted this cycle (≤ max_t1_per_cycle)
    t1_queue_depth: int  #: T1 candidates still waiting after the drain
    t2_executed: int  #: board slots granted this cycle (≤ max_t2_per_cycle)
    t2_queue_depth: int  #: T2 candidates still waiting after selection
    waited_over_one_cycle: int  #: queued cells passed over by >1 budget round
    cycle_time_ms: float
    promotions_by_reason: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TieringCycle:
    """Everything one :meth:`TierManager.run_cycle` decided, plus its metrics."""

    t1_batch: list[PromotionDecision]
    board_slots: list[BoardSlot]
    metrics: TieringMetrics


#: The pluggable expensive stage: runs the full forecast for a T1 batch and returns each
#: cell's fresh headline risk. In production this is the Session-22 slow path; in tests
#: and stress runs, a stub.
T1Runner = Callable[[Sequence[PromotionDecision]], Mapping[CellId, float]]


def _env_int(explicit: int | None, default: int, *names: str) -> int:
    """Resolve a budget: explicit arg > first set env var in ``names`` > default."""
    if explicit is not None:
        return explicit
    for name in names:
        raw = os.environ.get(name)
        if raw:
            return int(raw)
    return default


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
        risk_change_threshold: float = DEFAULT_RISK_CHANGE_THRESHOLD,
        max_t1_per_cycle: int | None = None,
        max_t2_per_cycle: int | None = None,
        watchlist_refresh_cycles: int | None = None,
    ) -> None:
        self._t1_score_cutoff = t1_score_cutoff
        self._band_low, self._band_high = transition_band
        self._belief_shift_threshold = belief_shift_threshold
        #: minimum score rise vs the previous cycle to count as "trending up" — damps
        #: float jitter from re-screening near-identical state.
        self._trend_epsilon = trend_epsilon
        self._risk_change_threshold = risk_change_threshold
        #: hard per-cycle cap on full Monte Carlo + Bayesian runs — the T1 compute budget.
        self._max_t1 = _env_int(max_t1_per_cycle, 64, "VECTIS_MAX_T1_PER_CYCLE")
        #: hard global cap on board/LLM narrations per cycle — the T2 budget.
        self._max_t2 = _env_int(
            max_t2_per_cycle, 5, "VECTIS_MAX_T2_PER_CYCLE", "VECTIS_MAX_BOARD_REPORTS_PER_CYCLE"
        )
        #: guaranteed T1 refresh cadence for pinned cells (Session 38): every Nth cycle a
        #: watchlisted cell gets a T1 slot even when no promotion gate fires.
        self._watchlist_refresh = _env_int(
            watchlist_refresh_cycles, 3, "VECTIS_WATCHLIST_REFRESH_CYCLES"
        )

        #: previous cycle's screen score per cell — the memory the trend gate reads.
        self._last_score: dict[CellId, float] = {}
        #: T1 candidates awaiting a deep-analysis slot, latest decision per cell.
        self._t1_queue: dict[CellId, PromotionDecision] = {}
        #: T2 candidates awaiting a board slot; losers of a budget round wait here.
        self._t2_queue: dict[CellId, BoardSlot] = {}
        #: headline risk at each cell's last granted board report — re-arms the change gate.
        self._last_reported_risk: dict[CellId, float] = {}
        #: budget rounds each queued cell has been passed over — the queue-aging signal.
        self._t1_waits: dict[CellId, int] = {}
        self._t2_waits: dict[CellId, int] = {}
        self._cycle = 0
        #: operator-pinned cells (Session 38) — synced from the AttentionRegistry each cycle.
        self._watchlist: frozenset[CellId] = frozenset()
        #: cycle number of each pinned cell's last granted T1 slot — the refresh schedule.
        self._watchlist_last_t1: dict[CellId, int] = {}

    def set_watchlist(self, cells: Iterable[CellId]) -> None:
        """Sync the operator watchlist. Pinned cells get a guaranteed T1 refresh every
        ``watchlist_refresh_cycles`` and jump the T1/T2 queues — **within** the same hard
        budgets: a pin wins priority for a slot, it never mints an extra one."""
        pinned = frozenset(cells)
        if unpinned := self._watchlist - pinned:
            for cell_id in unpinned:  # forget schedules for cells no longer pinned
                self._watchlist_last_t1.pop(cell_id, None)
        self._watchlist = pinned

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
        """Evaluate one sweep's worth of cells; enqueue and return the *new* promotions.

        A cell already awaiting its T1 slot is refreshed with this cycle's evidence
        (freshest state wins — the Session-22 coalescing principle at queue level) rather
        than counted as a second promotion. A queued cell that no longer qualifies stays
        queued — waiting, never silently dropped — but its priority is re-anchored to the
        current score, so a cooled-off cell sinks instead of holding a stale hot slot.

        Also records each cell's score as the next cycle's trend baseline — a mid-band
        cell first seen this cycle has no trend yet, so it can only promote next cycle
        (or immediately, via the score/belief gates).
        """
        shifts = belief_shifts or {}
        promoted: list[PromotionDecision] = []
        for cell_id, score in scores.items():
            decision = self.evaluate(cell_id, score, shifts.get(cell_id, 0.0))
            if decision is not None:
                if cell_id not in self._t1_queue:
                    promoted.append(decision)
                    self._t1_waits[cell_id] = 0
                    logger.debug(
                        "[TIER] promote %s -> T1 (%s: score=%.1f shift=%.3f prio=%.1f)",
                        cell_id, decision.reason, score, decision.belief_shift, decision.priority,
                    )
                self._t1_queue[cell_id] = decision  # freshest evidence wins
            elif cell_id in self._t1_queue:
                in_band = self._band_low <= score < self._band_high
                corrected = score + (MAX_MEASURED_UNDERESTIMATE if in_band else 0.0)
                self._t1_queue[cell_id] = replace(
                    self._t1_queue[cell_id], score=score, priority=corrected
                )
            self._last_score[cell_id] = score

        # Watchlist refresh (Session 38): a pinned cell whose scheduled refresh is due
        # enters the T1 queue even when no gate fired — independent of the screening
        # thresholds, so an operator's pin is never starved by a quiet score. It still
        # competes inside the same hard T1 budget (see drain_t1's priority order).
        for cell_id in self._watchlist:
            pin_score = scores.get(cell_id)
            if pin_score is None:
                continue  # no screenable state → nothing to forecast; never fabricate
            due = self._cycle - self._watchlist_last_t1.get(cell_id, -self._watchlist_refresh)
            if due >= self._watchlist_refresh and cell_id not in self._t1_queue:
                decision = PromotionDecision(
                    cell_id, "watchlist_refresh", pin_score, shifts.get(cell_id, 0.0), pin_score
                )
                self._t1_queue[cell_id] = decision
                self._t1_waits[cell_id] = 0
                promoted.append(decision)
        return promoted

    @property
    def t1_queue_depth(self) -> int:
        """T1 candidates still waiting for a deep-analysis slot."""
        return len(self._t1_queue)

    def drain_t1(self) -> list[PromotionDecision]:
        """Grant this cycle's deep-analysis slots: the top ``max_t1_per_cycle`` by priority.

        Priority is the bias-corrected promotion signal (see :meth:`evaluate`), so a
        transition-band cell competes as the risk it *may really be*. Watchlisted cells
        rank ahead of everything (Session 38): a pin wins priority for a slot inside the
        same hard budget, it never creates an extra one — with more pins than budget,
        pins compete among themselves by the same signal. Cells that don't make the cut
        are **not dropped** — they remain queued and are reconsidered next cycle, when
        their screening score (and hence rank) may have moved.
        """
        ranked = sorted(
            self._t1_queue.values(),
            key=lambda d: (d.cell_id in self._watchlist, d.priority),
            reverse=True,
        )
        batch = ranked[: self._max_t1]
        for decision in batch:
            del self._t1_queue[decision.cell_id]
            self._t1_waits.pop(decision.cell_id, None)
            if decision.cell_id in self._watchlist:
                self._watchlist_last_t1[decision.cell_id] = self._cycle  # refresh served
        for cell_id in self._t1_queue:  # everyone left was passed over one more round
            self._t1_waits[cell_id] = self._t1_waits.get(cell_id, 0) + 1
        return batch

    # ── T1 → T2 ───────────────────────────────────────────────────────────────────
    @property
    def t2_queue_depth(self) -> int:
        """T2 candidates still waiting for a board slot."""
        return len(self._t2_queue)

    def select_t2(self, risks: Mapping[CellId, float]) -> list[BoardSlot]:
        """Grant this cycle's board slots: the Session-22 change gate, then the hard budget.

        ``risks`` are the fresh T1 headline risks computed this cycle. Two gates compose:

        1. **Change gate** — the pipeline's own :func:`risk_moved` at global scope: a fresh
           risk becomes a T2 candidate only if it moved materially since the cell's last
           report. A *queued* candidate whose fresh risk no longer moves materially is
           withdrawn (the change it was queued for evaporated); with no fresh risk this
           cycle it waits unchanged.
        2. **Budget gate** — of all queued candidates, only the top ``max_t2_per_cycle`` by
           magnitude of change (== absolute risk for a never-reported cell) get a slot.
           Losers **wait** in the queue for the next cycle — never silently dropped.

        A cell can pass the change gate and still lose the budget gate when hotter cells
        compete for the same slots. Granted cells are recorded as reported, which is what
        re-arms their change gate for the next material move.

        Watchlisted cells (Session 38) get two boosts, both inside the same hard budget:
        candidacy on **any threshold crossing** — a risk-band boundary crossed since the
        last report counts even when the numeric move alone is immaterial — and first
        rank in the queue, so a pin wins a slot over a larger unpinned change rather
        than minting an extra narration.
        """
        for cell_id, risk in risks.items():
            prior = self._last_reported_risk.get(cell_id)
            watchlisted = cell_id in self._watchlist
            crossed_band = (
                watchlisted
                and prior is not None
                and RiskBand.from_score(prior) is not RiskBand.from_score(risk)
            )
            if risk_moved(prior, risk, self._risk_change_threshold) or crossed_band:
                change = abs(risk - prior) if prior is not None else risk
                self._t2_queue[cell_id] = BoardSlot(cell_id, risk, change, watchlisted)
                self._t2_waits.setdefault(cell_id, 0)
            else:
                self._t2_queue.pop(cell_id, None)  # pending change evaporated
                self._t2_waits.pop(cell_id, None)

        ranked = sorted(
            self._t2_queue.values(), key=lambda s: (s.watchlisted, s.change), reverse=True
        )
        granted = ranked[: self._max_t2]
        for slot in granted:
            del self._t2_queue[slot.cell_id]
            self._t2_waits.pop(slot.cell_id, None)
            self._last_reported_risk[slot.cell_id] = slot.risk
            logger.debug(
                "[TIER] board slot -> %s (risk=%.1f, change=%.1f)",
                slot.cell_id, slot.risk, slot.change,
            )
        for cell_id in self._t2_queue:  # everyone left was passed over one more round
            self._t2_waits[cell_id] = self._t2_waits.get(cell_id, 0) + 1
        return granted

    # ── one full cycle, with the numbers an operator watches ─────────────────────
    def run_cycle(
        self,
        scores: Mapping[CellId, float],
        belief_shifts: Mapping[CellId, float] | None = None,
        *,
        t1_runner: T1Runner | None = None,
    ) -> TieringCycle:
        """Run one complete tiering cycle: consider → drain T1 → run → select T2.

        ``t1_runner`` is the expensive stage (Monte Carlo + Bayesian) applied to the
        granted T1 batch; it returns each cell's fresh headline risk, which feeds the T2
        selection. Without a runner the T2 stage still runs — queued waiters from earlier
        cycles can win slots — but no new candidates arrive. Returns the batch, the board
        slots, and the cycle's :class:`TieringMetrics`.
        """
        start = time.perf_counter()
        self._cycle += 1

        promoted = self.consider(scores, belief_shifts)
        batch = self.drain_t1()
        risks = t1_runner(batch) if t1_runner is not None and batch else {}
        slots = self.select_t2(risks)

        waited = sum(
            1 for w in (*self._t1_waits.values(), *self._t2_waits.values()) if w > 1
        )
        reasons: Counter[str] = Counter(d.reason for d in promoted)
        metrics = TieringMetrics(
            cycle=self._cycle,
            hot_set_size=len(scores),
            t1_promoted=len(promoted),
            t1_executed=len(batch),
            t1_queue_depth=len(self._t1_queue),
            t2_executed=len(slots),
            t2_queue_depth=len(self._t2_queue),
            waited_over_one_cycle=waited,
            cycle_time_ms=(time.perf_counter() - start) * 1000.0,
            promotions_by_reason=dict(reasons),
        )
        return TieringCycle(t1_batch=batch, board_slots=slots, metrics=metrics)


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
