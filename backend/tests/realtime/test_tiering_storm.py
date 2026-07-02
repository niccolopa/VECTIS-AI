"""Session 33 — the global storm stress test.

The tiering engine's whole reason to exist: when thousands of cells cross the T1
threshold **simultaneously**, the expensive tiers must stay strictly budget-bounded and
degrade gracefully — a deeper queue, never a melted cycle — and recover to steady state
once the storm subsides. This test simulates exactly that against the *real* Session-32
screening sweep over a real evicting store (reusing the Session-30 land-weighted point
generator, not a fourth cell generator), and **prints the measured numbers honestly** in
the ``make stress`` tradition, including the ones that reveal a real bottleneck.

Marked ``slow`` (a scale proof, not needed on every push: ``pytest -m "not slow"``).
Run it loudly via ``make storm``.
"""

from __future__ import annotations

import random
import time

import pytest

# Session 30's land-weighted point generator — sibling module, pytest prepend import mode.
from test_global_grid_scale import _random_land_point

from vectis.realtime.screening.sweep import GlobalScreeningSweep
from vectis.realtime.state.cell_id import assign_cell_id
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import EvictingStateStore, MemoryStateStore
from vectis.realtime.tiering import (
    PromotionDecision,
    TieringMetrics,
    TierManager,
    headline_scores,
)

_ACTIVE_CELLS = 20_000  #: the calm global hot set
_STORM_CELLS = 4_000  #: cells crossing the T1 threshold at once
_MAX_T1 = 256
_MAX_T2 = 8
_STORM_STARTS = 3  #: cycle the storm hits
_STORM_ENDS = 10  #: cycle the storm subsides (temperatures fall back)
_MAX_CYCLES = 60


def _mild(rng: random.Random, cell_id: str) -> WorldCellState:
    """Calm-world state: cool temperatures screen far below every promotion gate.

    A slice of the calm world also carries benign multi-hazard state (Session 35) —
    flood / quake / cyclone observations — so the storm runs over a genuinely
    multi-hazard active set with every registered index sweeping every cycle.
    """
    state = WorldCellState(
        cell_id=cell_id,
        temperature=rng.uniform(10.0, 16.0),
        extra={"wind_speed_kmh": rng.uniform(0.0, 40.0)},
    )
    roll = rng.random()
    if roll < 0.05:
        state.flood_alert_level = 1.0
        state.precipitation_mm = rng.uniform(0.0, 5.0)
    elif roll < 0.10:
        state.earthquake_magnitude = rng.uniform(4.5, 5.0)
    elif roll < 0.15:
        state.cyclone_alert_level = 1.0
    return state


def _storm(rng: random.Random, cell_id: str) -> WorldCellState:
    """Storm state: hot and windy — screens deep into the saturated high tail."""
    return WorldCellState(
        cell_id=cell_id,
        temperature=rng.uniform(36.0, 44.0),
        extra={"wind_speed_kmh": rng.uniform(40.0, 80.0)},
    )


@pytest.mark.slow
def test_global_storm_stays_bounded_and_recovers() -> None:
    rng = random.Random(33)

    # ── the calm world: a real active set on real H3 cells ──────────────────────────
    store: EvictingStateStore[WorldCellState] = EvictingStateStore(
        MemoryStateStore(), maxsize=_ACTIVE_CELLS + 5_000
    )
    while store.active_cells < _ACTIVE_CELLS:
        lat, lon = _random_land_point(rng)
        store.save_state(_mild(rng, assign_cell_id(lat, lon)))

    all_cells = [state.cell_id for state in store.active_states()]
    storm_cells = rng.sample(all_cells, _STORM_CELLS)

    sweep = GlobalScreeningSweep()
    mgr = TierManager(max_t1_per_cycle=_MAX_T1, max_t2_per_cycle=_MAX_T2)

    def t1_runner(batch: list[PromotionDecision]) -> dict[str, float]:
        # Stand-in for the Monte Carlo slow path: headline risk == the screen that
        # promoted the cell. The stress target is the tiering engine, not the sampler
        # (the sampler's own numbers are Session 13's stress test).
        return {d.cell_id: d.score for d in batch}

    promoted_ever: set[str] = set()
    served_ever: set[str] = set()
    rows: list[tuple[int, str, float, TieringMetrics]] = []
    calm_times: list[float] = []
    storm_times: list[float] = []
    recovered_at: int | None = None

    cycle_n = 0
    while cycle_n < _MAX_CYCLES:
        cycle_n += 1
        if cycle_n == _STORM_STARTS:  # thousands cross the threshold simultaneously
            for cell_id in storm_cells:
                store.save_state(_storm(rng, cell_id))
        if cycle_n == _STORM_ENDS:  # the storm subsides
            for cell_id in storm_cells:
                store.save_state(_mild(rng, cell_id))
        phase = "storm" if _STORM_STARTS <= cycle_n < _STORM_ENDS else "calm"

        start = time.perf_counter()
        scores = headline_scores(sweep.sweep_store(store))
        cycle = mgr.run_cycle(scores, t1_runner=t1_runner)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        m = cycle.metrics
        promoted_ever |= {d.cell_id for d in cycle.t1_batch} | set(mgr._t1_queue)
        served_ever |= {d.cell_id for d in cycle.t1_batch}
        (storm_times if phase == "storm" else calm_times).append(elapsed_ms)
        rows.append((cycle_n, phase, elapsed_ms, m))

        # ── the hard bounds: strictly enforced EVERY cycle, storm or not ───────────
        assert m.t1_executed <= _MAX_T1, f"cycle {cycle_n}: T1 budget breached"
        assert m.t2_executed <= _MAX_T2, f"cycle {cycle_n}: T2 budget breached"

        if recovered_at is None and cycle_n > _STORM_ENDS and m.t1_queue_depth == 0:
            recovered_at = cycle_n
        if recovered_at is not None and cycle_n >= recovered_at + 2:
            break  # two steady-state cycles observed after recovery — enough evidence

    # ── honest report (the numbers, good and bad) ───────────────────────────────────
    print(
        f"\nGLOBAL STORM: {_ACTIVE_CELLS} active cells, {_STORM_CELLS} crossing at once; "
        f"budgets T1={_MAX_T1}/cycle, T2={_MAX_T2}/cycle"
    )
    print(" cyc phase   ms     hot    promo  t1ex  t1q    t2ex  t2q    waited")
    for n, phase, ms, m in rows:
        print(
            f" {n:>3} {phase:<6} {ms:>7.1f} {m.hot_set_size:>6} {m.t1_promoted:>6}"
            f" {m.t1_executed:>5} {m.t1_queue_depth:>6} {m.t2_executed:>5}"
            f" {m.t2_queue_depth:>6} {m.waited_over_one_cycle:>7}"
        )
    calm_med = sorted(calm_times)[len(calm_times) // 2]
    storm_peak = max(storm_times)
    final = rows[-1][3]
    print(
        f"calm median cycle {calm_med:.1f} ms; storm peak {storm_peak:.1f} ms "
        f"({storm_peak / calm_med:.1f}x); recovered (T1 queue empty) at cycle {recovered_at}"
    )
    print(
        f"residual T2 backlog at end: {final.t2_queue_depth} cells -- the board budget "
        f"({_MAX_T2}/cycle) is the tightest bottleneck; a {_STORM_CELLS}-cell storm leaves "
        f"a narration backlog that drains at {_MAX_T2}/cycle (documented, not hidden)"
    )

    # ── graceful degradation & recovery ─────────────────────────────────────────────
    assert recovered_at is not None, "T1 queue never drained after the storm subsided"
    # Wait-don't-drop: every cell ever promoted was eventually served a T1 slot.
    assert served_ever >= promoted_ever
    assert final.t1_queue_depth == 0
    # The aging signal keeps flagging the genuine T2 backlog — that is the metric doing
    # its job, not a failure to recover (T1, the compute tier, is fully drained).
    assert final.waited_over_one_cycle > 0
    # Degradation is gradual, not catastrophic: the worst storm cycle costs a small
    # multiple of a calm one (sweep + sort dominate; both near-linear in the hot set).
    assert storm_peak < 20 * calm_med, (storm_peak, calm_med)
    # And the storm's T1 backlog drains monotonically once promotions stop.
    post = [m.t1_queue_depth for n, _, _, m in rows if n > _STORM_ENDS]
    assert all(a >= b for a, b in zip(post, post[1:], strict=False))
