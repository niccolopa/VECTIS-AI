"""Historical risk × belief trajectories — the queryable audit trail (Session 39).

Serves the ``cell_snapshots`` rows the shared compute loop persists: per-cell
trajectories for the drill-down, and time-sliced viewport frames for the terminal's
playback mode. Everything here reads through the Session-2 database layer
(``get_db``) — the same engine the rest of the API uses, no parallel access path.

Two honesty notes, carried from the writer's side:
- History exists only where T1/T2 actually ran (promotion or pin). A cell with no
  snapshots was never analyzed — that absence is information, not an error.
- Every historical number inherits the illustrative, uncalibrated coefficients it was
  computed with. Replay shows what the system *believed*, not what was *true*.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from vectis.database.models import CellSnapshot
from vectis.database.session import get_db

router = APIRouter(prefix="/api/v1/history", tags=["history"])

#: Hard row cap per query — playback slices client-side; unbounded scans don't ship.
_MAX_ROWS = 10_000


class HistoryPoint(BaseModel):
    ts: datetime
    risk: float
    confidence: float
    tier: str
    trigger: str
    hazard: str
    posterior: dict[str, float] = Field(description="Scenario belief at snapshot time.")
    report_id: str | None


class CellHistory(BaseModel):
    cell_id: str
    points: list[HistoryPoint] = Field(description="Chronological (oldest first).")


class FrameCell(BaseModel):
    cell_id: str
    lat: float
    lon: float
    risk: float
    confidence: float


class PlaybackFrame(BaseModel):
    ts: datetime
    cells: list[FrameCell]


class PlaybackResponse(BaseModel):
    start: datetime
    end: datetime
    frames: list[PlaybackFrame]


def _utc(dt: datetime) -> datetime:
    """Force a UTC-aware datetime. SQLite drops tzinfo on ``DateTime(timezone=True)``
    reads (Postgres ``timestamptz`` keeps it); snapshots are always written in UTC, so
    a naive value read back is UTC — attach it rather than compare naive-vs-aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _window(
    start: datetime | None, end: datetime | None
) -> tuple[datetime, datetime]:
    end = end or datetime.now(UTC)
    start = start or end - timedelta(hours=24)
    if start >= end:
        raise HTTPException(status_code=422, detail="start must precede end")
    return start, end


@router.get("/cells/{cell_id}", response_model=CellHistory)
def cell_history(
    cell_id: str,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=_MAX_ROWS),
    db: Session = Depends(get_db),
) -> CellHistory:
    """One cell's risk × confidence × belief trajectory over a time range."""
    start, end = _window(start, end)
    rows = db.scalars(
        select(CellSnapshot)
        .where(CellSnapshot.cell_id == cell_id, CellSnapshot.ts >= start, CellSnapshot.ts <= end)
        .order_by(CellSnapshot.ts)
        .limit(limit)
    ).all()
    return CellHistory(
        cell_id=cell_id,
        points=[
            HistoryPoint(
                ts=_utc(r.ts), risk=r.risk_score, confidence=r.confidence, tier=r.tier,
                trigger=r.trigger, hazard=r.hazard, posterior=r.posterior,
                report_id=r.report_id,
            )
            for r in rows
        ],
    )


@router.get("/frames", response_model=PlaybackResponse)
def playback_frames(
    west: float = Query(ge=-180.0, le=180.0),
    south: float = Query(ge=-90.0, le=90.0),
    east: float = Query(ge=-180.0, le=180.0),
    north: float = Query(ge=-90.0, le=90.0),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    steps: int = Query(default=24, ge=2, le=200),
    db: Session = Depends(get_db),
) -> PlaybackResponse:
    """Time-sliced viewport frames for playback: the map's history, scrubbable.

    ``steps`` even slices over the range; each frame carries every snapshotted cell's
    **latest state as of that slice** (forward-filled within the window, so a cell
    analyzed at 14:00 still paints at 15:00 rather than flickering out between
    snapshots). Cells with no snapshot in the window are absent — honestly.
    """
    start, end = _window(start, end)
    rows = db.scalars(
        select(CellSnapshot)
        .where(
            CellSnapshot.ts >= start, CellSnapshot.ts <= end,
            CellSnapshot.lat >= south, CellSnapshot.lat <= north,
            CellSnapshot.lon >= west, CellSnapshot.lon <= east,
        )
        .order_by(CellSnapshot.ts)
        .limit(_MAX_ROWS)
    ).all()

    span = (end - start) / steps
    frames: list[PlaybackFrame] = []
    latest: dict[str, CellSnapshot] = {}
    i = 0
    for step in range(1, steps + 1):
        cut = start + span * step
        while i < len(rows) and _utc(rows[i].ts) <= cut:
            latest[rows[i].cell_id] = rows[i]  # newest snapshot ≤ cut wins
            i += 1
        frames.append(
            PlaybackFrame(
                ts=cut,
                cells=[
                    FrameCell(
                        cell_id=s.cell_id, lat=s.lat, lon=s.lon,
                        risk=s.risk_score, confidence=s.confidence,
                    )
                    for s in latest.values()
                ],
            )
        )
    return PlaybackResponse(start=start, end=end, frames=frames)
