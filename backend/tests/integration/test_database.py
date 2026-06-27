"""Database foundation tests: engine, session, connectivity, repository.

These exercise the shared engine/session layer and the SQL repository against
the temporary SQLite database configured in conftest, validating the persistence
foundation independently of the API.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, text

from vectis.core.schemas import CriticReview, DecisionReport
from vectis.database.repository import SqlAnalysisRepository
from vectis.database.session import get_db, get_engine, get_sessionmaker, init_db, ping


@pytest.fixture(scope="module", autouse=True)
def _schema() -> None:
    """Ensure the schema exists for the DB tests."""
    init_db()


def test_ping_returns_true() -> None:
    assert ping() is True


def test_engine_executes_query() -> None:
    with get_engine().connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_init_db_creates_analyses_table() -> None:
    assert "analyses" in inspect(get_engine()).get_table_names()


def test_get_db_yields_usable_session() -> None:
    gen = get_db()
    session = next(gen)
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def _report(report_id: str) -> DecisionReport:
    return DecisionReport(
        id=report_id, region="liguria", area_label="Liguria, Italy",
        risk_score=42.0, confidence=0.7, summary="test",
        critic_review=CriticReview(approved=True), model_card_ref="liguria/test@v1",
        generated_at=datetime.now(UTC),
    )


def test_sql_repository_roundtrip() -> None:
    repo = SqlAnalysisRepository(get_sessionmaker())
    repo.save(_report("dbtest0001"))

    fetched = repo.get("dbtest0001")
    assert fetched is not None
    assert fetched.id == "dbtest0001"
    assert fetched.region == "liguria"

    recent_ids = [r["id"] for r in repo.list_recent(limit=10)]
    assert "dbtest0001" in recent_ids


def test_sql_repository_missing_returns_none() -> None:
    assert SqlAnalysisRepository(get_sessionmaker()).get("nope") is None
