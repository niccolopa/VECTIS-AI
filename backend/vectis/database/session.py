"""Database engine, session factory, and FastAPI session dependency.

This is the single source of truth for the SQLAlchemy engine. The engine and
session factory are created lazily and cached, so importing this module never
touches the database — settings are read on first use (after the environment is
configured, which matters for tests). PostGIS-backed PostgreSQL is the production
target; SQLite is supported for local/dev/test with no external services.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from vectis.core.config import get_settings
from vectis.core.logging import get_logger

log = get_logger(__name__)


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine (created on first call)."""
    url = get_settings().database_url
    # SQLite needs check_same_thread=False to be usable across FastAPI's threadpool.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    """Return the process-wide session factory bound to the engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables from the ORM metadata.

    Convenience for local/dev/test. In production, schema is managed by Alembic
    migrations (``alembic upgrade head``); see docs/development.md.
    """
    from vectis.database import models  # noqa: F401  (register models on Base.metadata)
    from vectis.database.base import Base

    Base.metadata.create_all(get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session, closed after use."""
    factory = get_sessionmaker()
    with factory() as session:
        yield session


def ping() -> bool:
    """Return True if the database answers a trivial query, else False."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # connectivity is a readiness signal, not a crash
        log.warning("db.ping_failed", error=str(exc))
        return False


def reset_engine_cache() -> None:
    """Dispose and clear the cached engine/sessionmaker (used by tests)."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
