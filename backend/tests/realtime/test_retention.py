"""Session 39 — the retention & roll-up policy, and proof the loop enforces it.

Policy under test: fine rows past the fine window fold into hourly (cell, hazard)
rollups (max risk preserved, never averaged into calm), and rollups past the horizon
are deleted. The last test proves the shared compute loop actually *calls* enforce on
its cadence — the policy is a running mechanism, not a documented intention.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import h3
from sqlalchemy import select

from vectis.database.models import CellSnapshot, CellSnapshotRollup
from vectis.database.session import get_sessionmaker, init_db
from vectis.realtime.attention import AttentionRegistry
from vectis.realtime.compute import SharedComputeLoop
from vectis.realtime.ingestion.manager import IngestionManager
from vectis.realtime.live_stream import GlobalIngestionBroadcaster
from vectis.realtime.retention import RetentionPolicy
from vectis.realtime.state.models import WorldCellState
from vectis.realtime.state.store import MemoryStateStore

CELL = h3.latlng_to_cell(34.0, -118.0, 5)
LAT, LON = h3.cell_to_latlng(CELL)


def _wipe() -> None:
    with get_sessionmaker()() as s:
        s.execute(CellSnapshot.__table__.delete().where(CellSnapshot.cell_id == CELL))
        s.execute(CellSnapshotRollup.__table__.delete().where(CellSnapshotRollup.cell_id == CELL))
        s.commit()


def _add(ts: datetime, risk: float, conf: float = 0.5) -> None:
    with get_sessionmaker()() as s:
        s.add(CellSnapshot(
            cell_id=CELL, ts=ts, lat=LAT, lon=LON, tier="T1", trigger="t1_forecast",
            hazard="wildfire", risk_score=risk, confidence=conf,
            posterior={"a": 1.0}, screening={"wildfire": risk}, state=None, report_id=None,
        ))
        s.commit()


def _rollups() -> list[CellSnapshotRollup]:
    with get_sessionmaker()() as s:
        return list(s.scalars(
            select(CellSnapshotRollup).where(CellSnapshotRollup.cell_id == CELL)
            .order_by(CellSnapshotRollup.bucket)
        ))


def _fine_count() -> int:
    with get_sessionmaker()() as s:
        return len(list(s.scalars(select(CellSnapshot).where(CellSnapshot.cell_id == CELL))))


def test_old_fine_rows_fold_into_hourly_buckets_preserving_the_spike() -> None:
    init_db()
    _wipe()
    now = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    base = now - timedelta(days=10)  # older than the 7-day fine window
    # Three rows inside one hour: a calm pair and a spike. Plus one recent row that stays.
    _add(base.replace(minute=5), 20.0)
    _add(base.replace(minute=25), 30.0)
    _add(base.replace(minute=55), 95.0)  # the spike
    _add(now - timedelta(hours=1), 50.0)  # inside fine window — must NOT roll up

    policy = RetentionPolicy(fine_days=7, rollup_days=90)
    result = policy.enforce(now=now)

    assert result.rolled_fine_rows == 3
    assert result.buckets_written == 1
    assert _fine_count() == 1, "the recent row stays fine-grained"

    (bucket,) = _rollups()
    assert bucket.count == 3
    assert bucket.risk_max == 95.0, "the spike survives roll-up, never averaged into calm"
    assert abs(bucket.risk_mean - (20 + 30 + 95) / 3) < 1e-9
    assert bucket.bucket.replace(tzinfo=UTC) == base.replace(minute=0, second=0, microsecond=0)


def test_rollups_past_the_horizon_are_expired() -> None:
    init_db()
    _wipe()
    now = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
    # A fine row 200 days old → rolls up, then that bucket is already past the 90-day horizon.
    _add(now - timedelta(days=200), 40.0)
    policy = RetentionPolicy(fine_days=7, rollup_days=90)
    result = policy.enforce(now=now)

    assert result.buckets_written == 1
    assert result.expired_rollups == 1, "a bucket older than the horizon is deleted same pass"
    assert _rollups() == []


def test_the_compute_loop_enforces_retention_on_its_cadence() -> None:
    """The real-mechanism claim: run_cycle calls the policy every N ticks."""
    init_db()
    calls: list[int] = []

    class _Spy(RetentionPolicy):
        def enforce(self, *, now: datetime | None = None):  # type: ignore[override]
            calls.append(1)
            return super().enforce(now=now)

    store: MemoryStateStore[WorldCellState] = MemoryStateStore()
    loop = SharedComputeLoop(
        store=store,
        attention=AttentionRegistry(),
        ingestion=GlobalIngestionBroadcaster(store, manager=IngestionManager([])),
        retention=_Spy(),
        retention_every=3,  # ticks 0 and 3 fire within four cycles
    )
    for _ in range(4):
        loop.run_cycle()

    assert calls == [1, 1], "enforced on tick 0 and tick 3 — a running cadence, not a doc"
