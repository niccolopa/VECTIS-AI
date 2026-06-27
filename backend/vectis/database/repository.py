"""Analysis repository with a SQL-backed and an in-memory implementation."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from vectis.core.logging import get_logger
from vectis.core.schemas import DecisionReport
from vectis.database.models import AnalysisRecord

log = get_logger(__name__)


class AnalysisRepository(Protocol):
    """Stores and retrieves Decision Reports."""

    def save(self, report: DecisionReport) -> None: ...
    def get(self, analysis_id: str) -> DecisionReport | None: ...
    def list_recent(self, limit: int = 20) -> list[dict]: ...


def _summary(report: DecisionReport) -> dict:
    return {
        "id": report.id,
        "region": report.region,
        "area_label": report.area_label,
        "risk_score": report.risk_score,
        "risk_band": report.risk_band.value,
        "confidence": report.confidence,
        "approved": report.critic_review.approved,
        "generated_at": report.generated_at.isoformat(),
    }


class MemoryAnalysisRepository:
    """Process-local store — the fallback when no database is configured."""

    def __init__(self) -> None:
        self._store: dict[str, DecisionReport] = {}

    def save(self, report: DecisionReport) -> None:
        self._store[report.id] = report

    def get(self, analysis_id: str) -> DecisionReport | None:
        return self._store.get(analysis_id)

    def list_recent(self, limit: int = 20) -> list[dict]:
        reports = sorted(self._store.values(), key=lambda r: r.generated_at, reverse=True)
        return [_summary(r) for r in reports[:limit]]


class SqlAnalysisRepository:
    """Durable store backed by SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def save(self, report: DecisionReport) -> None:
        record = AnalysisRecord(
            id=report.id,
            region=report.region,
            risk_score=report.risk_score,
            confidence=report.confidence,
            approved=report.critic_review.approved,
            model_card_ref=report.model_card_ref,
            report=report.model_dump(mode="json"),
        )
        with self._session_factory() as session:
            session.merge(record)
            session.commit()

    def get(self, analysis_id: str) -> DecisionReport | None:
        with self._session_factory() as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is None:
                return None
            return DecisionReport.model_validate(record.report)

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._session_factory() as session:
            stmt = select(AnalysisRecord).order_by(
                AnalysisRecord.created_at.desc()).limit(limit)
            records = session.scalars(stmt).all()
            return [_summary(DecisionReport.model_validate(r.report)) for r in records]


def build_repository() -> AnalysisRepository:
    """Build a SQL repository if the database is reachable; else in-memory.

    Uses the shared engine/session factory from :mod:`vectis.database.session`,
    ensures the schema exists, and verifies connectivity before committing to the
    SQL path — otherwise it transparently falls back to in-memory storage so the
    demo and tests never require a database.
    """
    from vectis.database.session import get_sessionmaker, init_db, ping

    try:
        if not ping():
            raise RuntimeError("database did not respond to a connectivity check")
        init_db()
        log.info("repository.sql")
        return SqlAnalysisRepository(get_sessionmaker())
    except Exception as exc:  # DB not available — degrade to in-memory.
        log.warning("repository.memory_fallback", error=str(exc))
        return MemoryAnalysisRepository()
