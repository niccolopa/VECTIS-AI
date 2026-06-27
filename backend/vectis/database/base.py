"""SQLAlchemy declarative base.

The engine and session factory live in :mod:`vectis.database.session`; this module
holds only the declarative ``Base`` so ORM models can import it without pulling in
engine creation (avoiding import cycles).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
