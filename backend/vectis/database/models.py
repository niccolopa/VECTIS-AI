"""ORM models.

We persist each analysis as a row with the denormalized headline metrics (for
cheap listing/filtering) plus the full Decision Report as JSON (the source of
truth returned to clients).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from vectis.database.base import Base


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    approved: Mapped[bool] = mapped_column(Boolean)
    model_card_ref: Mapped[str] = mapped_column(String(128))
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class CellSnapshot(Base):
    """One persisted moment of a cell: state + risk + belief (Session 39).

    The durable history **underneath** the hot tier, never replacing it — the
    ``EvictingStateStore`` keeps serving live reads; these rows are what survives
    eviction and restart. Snapshot granularity (documented, structurally bounded):
    one row per **T1 forecast** (≤ ``max_t1_per_cycle``) and one per **T2 board
    report** (≤ ``max_t2_per_cycle``) — the tiering budgets bound the write rate, so
    persistence can never melt under a global storm. Screening-only updates are NOT
    snapshotted (100k/cycle would be, honestly, a log of an uncalibrated point
    estimate). ``posterior`` is the belief-trajectory entry; ``risk_score`` ×
    ``confidence`` over ``ts`` is the queryable history. Auditability, not accuracy:
    every number here inherits the models' illustrative coefficients.
    """

    __tablename__ = "cell_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cell_id: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    tier: Mapped[str] = mapped_column(String(2))  # "T1" | "T2" at snapshot time
    trigger: Mapped[str] = mapped_column(String(16))  # "t1_forecast" | "board_report"
    hazard: Mapped[str] = mapped_column(String(16))  # worst hazard the forecast ran on
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    posterior: Mapped[dict] = mapped_column(JSON)  # scenario → weight (belief trajectory)
    screening: Mapped[dict] = mapped_column(JSON)  # per-hazard T0 scores at snapshot time
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # observed variables
    report_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_cell_snapshots_cell_ts", "cell_id", "ts"),)
