"""Persistence layer: ORM base/models, engine/session management, repository.

Persistence is deliberately optional at runtime: the API uses a SQL-backed
repository when a database is reachable (PostgreSQL/PostGIS in docker-compose)
and transparently falls back to an in-memory repository otherwise, so the demo
and tests run with zero external services. The engine is a single shared source
in :mod:`vectis.database.session`; schema in production is managed by Alembic.
"""

from vectis.database.base import Base
from vectis.database.repository import (
    AnalysisRepository,
    MemoryAnalysisRepository,
    SqlAnalysisRepository,
    build_repository,
)
from vectis.database.session import get_db, get_engine, get_sessionmaker, init_db, ping

__all__ = [
    "Base",
    "get_db",
    "get_engine",
    "get_sessionmaker",
    "init_db",
    "ping",
    "AnalysisRepository",
    "MemoryAnalysisRepository",
    "SqlAnalysisRepository",
    "build_repository",
]
