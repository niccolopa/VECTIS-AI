"""Retention & roll-up — bounding the durable history in time (Session 39).

The ``cell_snapshots`` table would otherwise grow without limit: the tiering budgets
bound the *write rate*, but not the *horizon*. This policy bounds the horizon, so
storage is a function of "how many cells are watched", never "how long the system has
run".

**The exact policy** (all three windows configurable via env, defaults below):

- **Fine window — 7 days** (``VECTIS_HISTORY_FINE_DAYS``): every ``CellSnapshot`` row is
  kept verbatim. The trajectory API and playback serve full resolution here.
- **Roll-up — hourly, for snapshots older than the fine window**: fine rows past 7 days
  are folded into one ``CellSnapshotRollup`` per (cell, hazard, hour) — count, mean risk,
  **max risk** (a spike is never averaged into calm), mean confidence — and the folded
  fine rows are then deleted. Older history survives at hourly resolution.
- **Roll-up horizon — 90 days** (``VECTIS_HISTORY_ROLLUP_DAYS``): rollup buckets older
  than 90 days are deleted outright. Beyond 90 days there is no history — bounded and
  documented, not silently unbounded.

This makes storage bounded: at most ``fine_days`` of fine rows (at the budgeted write
rate) plus at most ``rollup_days × 24`` buckets per (cell, hazard) that was ever
promoted. It is enforced by :meth:`RetentionPolicy.enforce`, which the shared compute
loop calls on a cadence — a real mechanism, not a documented intention.

Auditability, not accuracy: every rolled-up number inherits the illustrative
coefficients the snapshot was computed with. Roll-up only *coarsens* what was believed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from vectis.core.logging import get_logger
from vectis.database.models import CellSnapshot, CellSnapshotRollup
from vectis.database.session import get_sessionmaker

logger = get_logger(__name__)


def _utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on read; snapshots are written UTC, so attach it if naive."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _hour(dt: datetime) -> datetime:
    return _utc(dt).replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class RetentionResult:
    """What one enforce() pass did — the numbers the persistence proof asserts on."""

    rolled_fine_rows: int = 0
    buckets_written: int = 0
    expired_rollups: int = 0


class RetentionPolicy:
    """Fold fine snapshots older than the fine window into hourly rollups; expire old rollups."""

    def __init__(
        self,
        *,
        fine_days: int | None = None,
        rollup_days: int | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.fine_days = fine_days if fine_days is not None else int(
            os.getenv("VECTIS_HISTORY_FINE_DAYS", "7")
        )
        self.rollup_days = rollup_days if rollup_days is not None else int(
            os.getenv("VECTIS_HISTORY_ROLLUP_DAYS", "90")
        )
        self._factory: Callable[[], Session] | None = session_factory

    def _session(self) -> Session:
        if self._factory is None:
            self._factory = get_sessionmaker()
        return self._factory()

    def enforce(self, *, now: datetime | None = None) -> RetentionResult:
        """Run one retention pass. Best-effort: a DB hiccup is logged, never raised."""
        now = now or datetime.now(UTC)
        fine_cutoff = now - timedelta(days=self.fine_days)
        rollup_cutoff = now - timedelta(days=self.rollup_days)
        try:
            with self._session() as session:
                result = self._rollup(session, fine_cutoff)
                expired = self._expire(session, rollup_cutoff)
                session.commit()
                return RetentionResult(
                    rolled_fine_rows=result[0],
                    buckets_written=result[1],
                    expired_rollups=expired,
                )
        except Exception:
            logger.exception("[ERROR] retention pass failed; history not pruned this cycle")
            return RetentionResult()

    def _rollup(self, session: Session, fine_cutoff: datetime) -> tuple[int, int]:
        """Fold fine rows older than the cutoff into hourly (cell, hazard) buckets.

        Aggregation is done in Python (portable across SQLite/Postgres, no dialect
        date_trunc). ponytail: fine, since the batch each pass is bounded by the write
        rate over one cadence interval; move to a SQL GROUP BY date_trunc if a single
        pass ever folds millions of rows.
        """
        old = list(
            session.scalars(
                select(CellSnapshot).where(CellSnapshot.ts < fine_cutoff).order_by(CellSnapshot.ts)
            )
        )
        if not old:
            return (0, 0)

        # Group by (cell_id, hazard, hour). Merge with any existing bucket already stored.
        agg: dict[tuple[str, str, datetime], list[CellSnapshot]] = {}
        for row in old:
            agg.setdefault((row.cell_id, row.hazard, _hour(row.ts)), []).append(row)

        buckets_written = 0
        for (cell_id, hazard, bucket), rows in agg.items():
            existing = session.scalar(
                select(CellSnapshotRollup).where(
                    CellSnapshotRollup.cell_id == cell_id,
                    CellSnapshotRollup.hazard == hazard,
                    CellSnapshotRollup.bucket == bucket,
                )
            )
            risks = [r.risk_score for r in rows]
            confs = [r.confidence for r in rows]
            n_new = len(rows)
            if existing is None:
                session.add(
                    CellSnapshotRollup(
                        cell_id=cell_id, hazard=hazard, bucket=bucket,
                        lat=rows[-1].lat, lon=rows[-1].lon, count=n_new,
                        risk_mean=sum(risks) / n_new, risk_max=max(risks),
                        confidence_mean=sum(confs) / n_new,
                    )
                )
                buckets_written += 1
            else:
                # Weighted merge into the existing bucket (a later pass re-touched this hour).
                total = existing.count + n_new
                existing.risk_mean = (
                    existing.risk_mean * existing.count + sum(risks)
                ) / total
                existing.confidence_mean = (
                    existing.confidence_mean * existing.count + sum(confs)
                ) / total
                existing.risk_max = max(existing.risk_max, *risks)
                existing.count = total

        ids = [r.id for r in old]
        session.execute(delete(CellSnapshot).where(CellSnapshot.id.in_(ids)))
        return (len(old), buckets_written)

    def _expire(self, session: Session, rollup_cutoff: datetime) -> int:
        """Delete rollup buckets older than the horizon — bounded history, honestly."""
        stale = list(
            session.scalars(
                select(CellSnapshotRollup.id).where(CellSnapshotRollup.bucket < rollup_cutoff)
            )
        )
        if stale:
            session.execute(
                delete(CellSnapshotRollup).where(CellSnapshotRollup.id.in_(stale))
            )
        return len(stale)
