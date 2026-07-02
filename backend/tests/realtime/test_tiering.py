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


# ── Step 2: T1 → T2 — the change gate composes with a hard board budget ────────────────
def test_board_budget_is_a_hard_cap_no_matter_how_many_cells_moved() -> None:
    mgr = TierManager(max_t2_per_cycle=3)
    granted = mgr.select_t2({f"c{i}": 50.0 + i for i in range(10)})  # all pass the change gate
    assert len(granted) == 3
    # The hottest changes won the slots; the other 7 WAIT in the queue, not dropped.
    assert [s.cell_id for s in granted] == ["c9", "c8", "c7"]
    assert mgr.t2_queue_depth == 7


def test_unmoved_risk_fails_the_change_gate_even_with_budget_free() -> None:
    # Composition with the Session-22 gate: budget alone is not enough — the risk must
    # have moved materially since the cell's last report.
    mgr = TierManager(max_t2_per_cycle=5, risk_change_threshold=5.0)
    assert [s.cell_id for s in mgr.select_t2({"cell": 50.0})] == ["cell"]  # first look
    granted = mgr.select_t2({"cell": 52.0})  # moved only 2 < 5 → gated out
    assert granted == []
    assert mgr.t2_queue_depth == 0  # not queued either: there is no material change to report


def test_cell_can_pass_change_gate_and_still_lose_the_budget_gate() -> None:
    mgr = TierManager(max_t2_per_cycle=1)
    # Both moved materially; only the bigger move gets this cycle's one slot.
    [winner] = mgr.select_t2({"small_move": 40.0, "big_move": 90.0})
    assert winner.cell_id == "big_move"
    # The loser waits — and wins the next cycle's slot with no new input needed.
    [next_winner] = mgr.select_t2({})
    assert next_winner.cell_id == "small_move"
    assert mgr.t2_queue_depth == 0


def test_queued_candidate_is_withdrawn_when_its_change_evaporates() -> None:
    mgr = TierManager(max_t2_per_cycle=1, risk_change_threshold=5.0)
    mgr.select_t2({"stale": 48.0, "hot": 90.0})  # hot wins the slot; stale waits
    [slot] = mgr.select_t2({})  # next cycle: stale gets its slot, reported at 48
    assert slot.cell_id == "stale"
    mgr.select_t2({"stale": 90.0, "hot2": 95.0})  # stale re-queued (moved 42), loses to hot2
    assert mgr.t2_queue_depth == 1
    # Fresh risk falls back to ~its last report: the material change it was queued for no
    # longer exists, so it is withdrawn — reporting it would narrate a non-change.
    granted = mgr.select_t2({"stale": 50.0})
    assert granted == []
    assert mgr.t2_queue_depth == 0


def test_granted_report_rearms_the_change_gate() -> None:
    mgr = TierManager(max_t2_per_cycle=5, risk_change_threshold=5.0)
    mgr.select_t2({"cell": 60.0})  # reported at 60
    assert mgr.select_t2({"cell": 60.0}) == []  # same risk → no re-report churn
    [slot] = mgr.select_t2({"cell": 70.0})  # material move → reports again
    assert slot.change == 10.0


def test_t2_budget_reads_the_env_knob(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("VECTIS_MAX_BOARD_REPORTS_PER_CYCLE", "2")
    mgr = TierManager()
    assert len(mgr.select_t2({f"c{i}": 50.0 + i for i in range(6)})) == 2


# ── Step 3: the T1 priority queue — budgeted draining, waiting instead of dropping ─────
def test_t1_drain_is_hard_bounded_and_highest_priority_first() -> None:
    mgr = TierManager(max_t1_per_cycle=3)
    mgr.consider({f"c{i}": 85.0 + i * 0.1 for i in range(10)})  # 10 tail promotions
    batch = mgr.drain_t1()
    assert len(batch) == 3
    assert [d.cell_id for d in batch] == ["c9", "c8", "c7"]  # hottest first
    assert mgr.t1_queue_depth == 7  # the rest wait


def test_cells_that_miss_the_cut_wait_and_are_all_eventually_served() -> None:
    # The whole point of the queue: a legitimately risky cell is never silently discarded.
    mgr = TierManager(max_t1_per_cycle=4)
    promoted = {d.cell_id for d in mgr.consider({f"c{i}": 90.0 + i * 0.01 for i in range(10)})}
    served: set[str] = set()
    for _ in range(3):  # 10 cells / budget 4 → 3 cycles to serve everyone
        served |= {d.cell_id for d in mgr.drain_t1()}
    assert served == promoted
    assert mgr.t1_queue_depth == 0


def test_bias_corrected_band_cell_outranks_a_higher_raw_tail_score() -> None:
    # The shape-awareness must reach the *ranking* too: a mid-band cell at 80 may really
    # be ~93 (measured under-read), so it drains before a saturated-tail cell at 90.
    mgr = TierManager(max_t1_per_cycle=1)
    mgr.consider({"band": 80.0, "tail": 90.0})  # band cell: no trend yet, not promoted
    mgr.consider({"band": 84.0, "tail": 90.0})  # band trends up → promoted at 84+13.23
    [first] = mgr.drain_t1()
    assert first.cell_id == "band"
    assert first.priority > 90.0


def test_waiting_cell_is_reranked_by_fresh_evidence_not_its_stale_score() -> None:
    mgr = TierManager(max_t1_per_cycle=1)
    mgr.consider({"a": 95.0, "b": 90.0})
    mgr.drain_t1()  # a served; b waits at priority 90
    # Next sweep b has cooled to 10 while c crosses the cutoff: c must outrank the
    # cooled-off waiter — but b still waits rather than being dropped.
    mgr.consider({"b": 10.0, "c": 88.0})
    [first] = mgr.drain_t1()
    assert first.cell_id == "c"
    assert mgr.t1_queue_depth == 1  # b still queued, at its refreshed (low) priority
    [leftover] = mgr.drain_t1()
    assert leftover.cell_id == "b"
    assert leftover.score == 10.0  # audit trail reflects the freshest evidence


def test_sustained_hot_cell_repromotes_after_being_served() -> None:
    # Persistent activity keeps earning T1 refreshes (bounded by the budget each cycle).
    mgr = TierManager(max_t1_per_cycle=8)
    assert len(mgr.consider({"cell": 95.0})) == 1
    mgr.drain_t1()
    assert len(mgr.consider({"cell": 95.0})) == 1  # re-promoted, not deduplicated forever


def test_requalifying_queued_cell_refreshes_in_place_not_as_a_second_entry() -> None:
    mgr = TierManager(max_t1_per_cycle=8)
    assert len(mgr.consider({"cell": 90.0})) == 1
    assert mgr.consider({"cell": 96.0}) == []  # refreshed, not double-promoted
    assert mgr.t1_queue_depth == 1
    [decision] = mgr.drain_t1()
    assert decision.score == 96.0  # the queue held the freshest evidence


def test_t1_budget_reads_the_env_knob(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("VECTIS_MAX_T1_PER_CYCLE", "2")
    mgr = TierManager()
    mgr.consider({f"c{i}": 90.0 for i in range(5)})
    assert len(mgr.drain_t1()) == 2


# ── Step 5: back-pressure metrics — the numbers an operator would actually watch ───────
def test_run_cycle_reports_the_full_back_pressure_picture() -> None:
    mgr = TierManager(max_t1_per_cycle=2, max_t2_per_cycle=1)
    scores = {f"hot{i}": 90.0 + i * 0.1 for i in range(4)} | {"cold": 1.0}

    cycle = mgr.run_cycle(scores, t1_runner=lambda batch: {d.cell_id: d.score for d in batch})

    m = cycle.metrics
    assert m.cycle == 1
    assert m.hot_set_size == 5  # everything screened, including the cold cell
    assert m.t1_promoted == 4 and m.t1_executed == 2 and m.t1_queue_depth == 2
    assert m.t2_executed == 1 and m.t2_queue_depth == 1  # both T1 risks were material
    assert m.promotions_by_reason == {"score_threshold": 4}
    assert m.cycle_time_ms > 0.0
    assert len(cycle.t1_batch) == 2 and len(cycle.board_slots) == 1


def test_waited_over_one_cycle_flags_queue_aging_not_a_brief_spike() -> None:
    mgr = TierManager(max_t1_per_cycle=1, max_t2_per_cycle=1)
    first = mgr.run_cycle({f"c{i}": 90.0 + i * 0.1 for i in range(3)})
    # Fresh backlog: two cells wait, but nobody has been passed over twice yet.
    assert first.metrics.t1_queue_depth == 2
    assert first.metrics.waited_over_one_cycle == 0
    second = mgr.run_cycle({})
    # One more round: the last cell has now been passed over twice — the queue is aging.
    assert second.metrics.t1_queue_depth == 1
    assert second.metrics.waited_over_one_cycle == 1
    third = mgr.run_cycle({})
    assert third.metrics.t1_queue_depth == 0
    assert third.metrics.waited_over_one_cycle == 0  # backlog cleared, signal resets


def test_run_cycle_without_a_runner_still_serves_queued_t2_waiters() -> None:
    mgr = TierManager(max_t1_per_cycle=8, max_t2_per_cycle=1)
    mgr.select_t2({"a": 60.0, "b": 80.0})  # b granted; a waits in the T2 queue
    cycle = mgr.run_cycle({})  # no sweep, no runner — but the waiter can still win
    assert [s.cell_id for s in cycle.board_slots] == ["a"]


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
