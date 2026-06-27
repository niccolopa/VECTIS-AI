"""ORM models.

We persist each analysis as a row with the denormalized headline metrics (for
cheap listing/filtering) plus the full Decision Report as JSON (the source of
truth returned to clients).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String
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
