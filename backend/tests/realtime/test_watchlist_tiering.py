"""Session 38 — watchlist priority in the tiering engine, actually wired.

A pin buys **freshness and queue priority**, never extra budget and never a better
number: the hard T1/T2 ceilings are unchanged, and a watchlisted forecast runs the same
uncalibrated models as everyone else's.
"""

from __future__ import annotations

from vectis.realtime.tiering.manager import BoardSlot, TierManager


def test_pinned_quiet_cell_gets_a_guaranteed_t1_refresh_on_schedule() -> None:
    mgr = TierManager(watchlist_refresh_cycles=3, max_t1_per_cycle=64)
    mgr.set_watchlist({"pinned"})

    # Score 3.0: below the band, no belief shift, no trend — no normal gate can fire.
    first = mgr.run_cycle({"pinned": 3.0}, t1_runner=lambda batch: {})
    assert [d.cell_id for d in first.t1_batch] == ["pinned"]
    assert first.t1_batch[0].reason == "watchlist_refresh"

    # Cycles 2 and 3: refresh not due yet — the pin does not burn budget every cycle.
    for _ in range(2):
        cycle = mgr.run_cycle({"pinned": 3.0}, t1_runner=lambda batch: {})
        assert cycle.t1_batch == []

    # Cycle 4: due again.
    fourth = mgr.run_cycle({"pinned": 3.0}, t1_runner=lambda batch: {})
    assert [d.cell_id for d in fourth.t1_batch] == ["pinned"]


def test_unpinned_cells_behave_exactly_as_before() -> None:
    mgr = TierManager(watchlist_refresh_cycles=3)
    cycle = mgr.run_cycle({"quiet": 3.0, "hot": 92.0}, t1_runner=lambda batch: {})
    assert [d.cell_id for d in cycle.t1_batch] == ["hot"], "no watchlist → no new promotions"


def test_pin_wins_t1_priority_but_never_extra_budget() -> None:
    mgr = TierManager(watchlist_refresh_cycles=1, max_t1_per_cycle=2)
    mgr.set_watchlist({"pinned"})

    # Three hot cells + one quiet pin compete for two slots: the pin takes one on
    # priority, the hottest unpinned cell takes the other, and the budget holds at 2.
    cycle = mgr.run_cycle(
        {"pinned": 10.0, "hot_a": 95.0, "hot_b": 92.0, "hot_c": 90.0},
        t1_runner=lambda batch: {},
    )
    granted = [d.cell_id for d in cycle.t1_batch]
    assert len(granted) == 2, "the hard T1 budget is unchanged by pinning"
    assert granted[0] == "pinned", "the pin outranks hotter unpinned cells"
    assert granted[1] == "hot_a"
    assert cycle.metrics.t1_queue_depth == 2, "losers wait, never dropped"


def test_pinned_cell_reaches_t2_on_a_band_crossing_too_small_to_move_materially() -> None:
    mgr = TierManager(max_t2_per_cycle=5, risk_change_threshold=5.0)
    mgr.set_watchlist({"pinned"})
    # First report anchors both cells' change gates.
    mgr.select_t2({"pinned": 74.0, "plain": 74.0})

    # 74 → 76 crosses the HIGH/SEVERE band boundary (75) but moves only 2 pts — below
    # the material-change threshold. The pin narrates; the identical unpinned cell waits.
    slots = mgr.select_t2({"pinned": 76.0, "plain": 76.0})
    assert [s.cell_id for s in slots] == ["pinned"]
    assert slots[0].watchlisted is True


def test_pin_wins_a_t2_slot_over_a_larger_unpinned_change_within_the_hard_budget() -> None:
    mgr = TierManager(max_t2_per_cycle=1, risk_change_threshold=5.0)
    mgr.set_watchlist({"pinned"})

    # Both changes are material; the unpinned one is larger. Budget is one slot.
    slots = mgr.select_t2({"pinned": 40.0, "plain": 90.0})
    assert len(slots) == 1, "the hard T2 ceiling is never exceeded for a pin"
    assert slots[0].cell_id == "pinned", "the pin wins priority for the slot"
    assert mgr.t2_queue_depth == 1, "the bigger unpinned change waits, not dropped"

    # Next cycle, with no fresh risks, the waiting unpinned cell gets its slot.
    assert [s.cell_id for s in mgr.select_t2({})] == ["plain"]


def test_unpinning_forgets_the_refresh_schedule() -> None:
    mgr = TierManager(watchlist_refresh_cycles=3)
    mgr.set_watchlist({"pinned"})
    first = mgr.run_cycle({"pinned": 3.0}, t1_runner=lambda batch: {})
    assert len(first.t1_batch) == 1

    mgr.set_watchlist(set())  # unpin — the quiet cell must fall back to normal gates
    for _ in range(4):
        cycle = mgr.run_cycle({"pinned": 3.0}, t1_runner=lambda batch: {})
        assert cycle.t1_batch == []


def test_board_slot_records_the_watchlist_provenance() -> None:
    slot = BoardSlot("cell", 50.0, 10.0)
    assert slot.watchlisted is False, "default stays audit-honest for unpinned slots"
