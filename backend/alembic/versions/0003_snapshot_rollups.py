"""retention roll-up: cell_snapshot_rollups

Session 39. Coarse older history — one hourly bucket per (cell, hazard) — that the
retention policy folds fine ``cell_snapshots`` rows into before deleting them, so
storage is bounded by time rather than by uptime. Mirrors
``vectis.database.models.CellSnapshotRollup``.

Revision ID: 0003_snapshot_rollups
Revises: 0002_cell_snapshots
Create Date: 2026-07-04
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_snapshot_rollups"
down_revision: str | None = "0002_cell_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cell_snapshot_rollups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cell_id", sa.String(length=32), nullable=False),
        sa.Column("hazard", sa.String(length=16), nullable=False),
        sa.Column("bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("risk_mean", sa.Float(), nullable=False),
        sa.Column("risk_max", sa.Float(), nullable=False),
        sa.Column("confidence_mean", sa.Float(), nullable=False),
    )
    op.create_index("ix_cell_snapshot_rollups_cell_id", "cell_snapshot_rollups", ["cell_id"])
    op.create_index("ix_cell_snapshot_rollups_bucket", "cell_snapshot_rollups", ["bucket"])
    op.create_index(
        "ix_cell_snapshot_rollups_cell_bucket",
        "cell_snapshot_rollups",
        ["cell_id", "hazard", "bucket"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_cell_snapshot_rollups_cell_bucket", table_name="cell_snapshot_rollups")
    op.drop_index("ix_cell_snapshot_rollups_bucket", table_name="cell_snapshot_rollups")
    op.drop_index("ix_cell_snapshot_rollups_cell_id", table_name="cell_snapshot_rollups")
    op.drop_table("cell_snapshot_rollups")
