"""Session 39 — the persistence proof (Step 10).

Three system-level guarantees, each proven against the real durable store rather than
asserted:

1. **Restart survival** — both tiers (fine snapshots *and* rolled-up buckets) outlive a
   process restart, read back through a fresh engine after the cached one is disposed.
2. **Bounded storage** — under the retention policy, total rows plateau over a long
   simulated horizon instead of growing with uptime.
3. **Roll-up consistency** — a bucket faithfully summarizes exactly the fine rows it
   replaced (count, mean, and the preserved max), with no silent loss or fabrication;
   the recent fine trajectory the API serves is left untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import h3
from sqlalchemy import func, select

from vectis.database.models import CellSnapshot, CellSnapshotRollup
from vectis.database.session import get_sessionmaker, init_db, reset_engine_cache
from vectis.realtime.retention import RetentionPolicy

A = h3.latlng_to_cell(34.0, -118.0, 5)
B = h3.latlng_to_cell(40.7, -74.0, 5)
CELLS = (A, B)


def _wipe() -> None:
    with get_sessionmaker()() as s:
        for cell in CELLS:
            s.execute(CellSnapshot.__table__.delete().where(CellSnapshot.cell_id == cell))
            s.execute(
                CellSnapshotRollup.__table__.delete().where(CellSnapshotRollup.cell_id == cell)
            )
        s.commit()


def _add(cell: str, ts: datetime, risk: float, conf: float = 0.5) -> None:
    lat, lon = h3.cell_to_latlng(cell)
    with get_sessionmaker()() as s:
        s.add(CellSnapshot(
            cell_id=cell, ts=ts, lat=lat, lon=lon, tier="T1", trigger="t1_forecast",
            hazard="wildfire", risk_score=risk, confidence=conf,
            posterior={"a": 1.0}, screening={"wildfire": risk}, state=None, report_id=None,
        ))
        s.commit()


def _counts() -> tuple[int, int]:
    with get_sessionmaker()() as s:
        fine = s.scalar(
            select(func.count()).select_from(CellSnapshot).where(CellSnapshot.cell_id.in_(CELLS))
        )
        roll = s.scalar(
            select(func.count()).select_from(CellSnapshotRollup)
            .where(CellSnapshotRollup.cell_id.in_(CELLS))
        )
        return int(fine or 0), int(roll or 0)


def test_both_history_tiers_survive_a_restart() -> None:
    init_db()
    _wipe()
    now = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    _add(A, now - timedelta(days=10), 80.0)      # will roll up
    _add(A, now - timedelta(hours=1), 55.0)      # stays fine
    RetentionPolicy(fine_days=7, rollup_days=90).enforce(now=now)
    fine_before, roll_before = _counts()
    assert (fine_before, roll_before) == (1, 1), "one fine row remains, one bucket written"

    # ── the restart: dispose the engine + every cached session factory ──
    reset_engine_cache()

    fine_after, roll_after = _counts()  # read through a brand-new engine, from disk
    assert (fine_after, roll_after) == (1, 1), "both tiers survived the restart"


def test_storage_is_bounded_over_a_long_horizon() -> None:
    """Simulate 40 days of hourly snapshots; total rows must plateau, not grow with time."""
    init_db()
    _wipe()
    policy = RetentionPolicy(fine_days=2, rollup_days=10)
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    totals: list[int] = []
    for day in range(40):
        today = start + timedelta(days=day)
        for cell in CELLS:
            for hour in (0, 6, 12, 18):
                _add(cell, today.replace(hour=hour), 30.0 + hour)
        policy.enforce(now=today + timedelta(hours=23))  # end-of-day retention sweep
        fine, roll = _counts()
        totals.append(fine + roll)

    naive = 40 * 4 * len(CELLS)  # what unbounded retention would have accumulated
    peak = max(totals)
    print("\n-- bounded-storage proof over a 40-day horizon --------------")
    print(f"unbounded (naive) total rows: {naive}")
    print(f"bounded peak total rows:      {peak}  (fine+rollup, both cells)")
    print(f"steady-state (last 10 days):  {totals[-10:]}")

    assert peak < naive, "retention keeps the total well under the unbounded count"
    # Plateau: the tail is flat — later days do not accumulate more than earlier steady state.
    assert totals[-1] <= totals[20], "storage stops growing once the horizon fills"
    assert max(totals[25:]) - min(totals[25:]) <= 8, "steady state is flat, not creeping up"


def test_rollup_summarizes_exactly_the_folded_rows() -> None:
    """No silent loss or fabrication: the bucket equals the fine rows it replaced."""
    init_db()
    _wipe()
    now = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    old_hour = (now - timedelta(days=10)).replace(minute=0, second=0, microsecond=0)
    # Four old rows in one hour (fold into one bucket) + two recent rows (stay fine).
    old_risks = [12.0, 48.0, 91.0, 33.0]
    for i, r in enumerate(old_risks):
        _add(A, old_hour + timedelta(minutes=i * 10), r, conf=0.4 + i * 0.1)
    _add(A, now - timedelta(hours=2), 60.0)
    _add(A, now - timedelta(hours=1), 65.0)

    RetentionPolicy(fine_days=7, rollup_days=90).enforce(now=now)

    with get_sessionmaker()() as s:
        buckets = list(s.scalars(
            select(CellSnapshotRollup).where(CellSnapshotRollup.cell_id == A)
        ))
        fine = list(s.scalars(
            select(CellSnapshot).where(CellSnapshot.cell_id == A).order_by(CellSnapshot.ts)
        ))

    assert len(buckets) == 1
    b = buckets[0]
    assert b.count == len(old_risks), "every folded row is accounted for — none lost"
    assert b.risk_max == max(old_risks), "the max is preserved exactly, not fabricated"
    assert abs(b.risk_mean - sum(old_risks) / len(old_risks)) < 1e-9, "mean is faithful"

    # The recent trajectory the playback/query API serves is untouched by roll-up.
    assert [round(r.risk_score) for r in fine] == [60, 65], "recent fine rows intact"
