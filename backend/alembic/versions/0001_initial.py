"""initial schema: analyses

Creates the ``analyses`` table that stores each Decision Report (denormalized
headline metrics plus the full report JSON). Mirrors
``vectis.database.models.AnalysisRecord``.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-26
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("model_card_ref", sa.String(length=128), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analyses_region", "analyses", ["region"])
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_analyses_created_at", table_name="analyses")
    op.drop_index("ix_analyses_region", table_name="analyses")
    op.drop_table("analyses")
