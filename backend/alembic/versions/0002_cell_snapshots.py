"""cell state + belief history: cell_snapshots

Session 39. One row per T1 forecast / T2 board report — the durable layer under the
hot tier. Mirrors ``vectis.database.models.CellSnapshot``. On PostgreSQL (the PostGIS
production target) an additional GiST index over the point geography accelerates the
playback endpoint's bbox scans; SQLite gets the portable btree indexes only.

Revision ID: 0002_cell_snapshots
Revises: 0001_initial
Create Date: 2026-07-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_cell_snapshots"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cell_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cell_id", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("tier", sa.String(length=2), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("hazard", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("posterior", sa.JSON(), nullable=False),
        sa.Column("screening", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("report_id", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_cell_snapshots_cell_id", "cell_snapshots", ["cell_id"])
    op.create_index("ix_cell_snapshots_ts", "cell_snapshots", ["ts"])
    op.create_index("ix_cell_snapshots_cell_ts", "cell_snapshots", ["cell_id", "ts"])
    if op.get_bind().dialect.name == "postgresql":
        # PostGIS spatial index for the playback bbox scans (production target).
        op.execute(
            "CREATE INDEX ix_cell_snapshots_geo ON cell_snapshots "
            "USING GIST (ST_SetSRID(ST_MakePoint(lon, lat), 4326))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_cell_snapshots_geo")
    op.drop_index("ix_cell_snapshots_cell_ts", table_name="cell_snapshots")
    op.drop_index("ix_cell_snapshots_ts", table_name="cell_snapshots")
    op.drop_index("ix_cell_snapshots_cell_id", table_name="cell_snapshots")
    op.drop_table("cell_snapshots")
