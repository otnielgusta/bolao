"""add ranking snapshots

Revision ID: b8f3a1c4d2e5
Revises: 42d3f0ad1b8c
Create Date: 2026-06-13 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f3a1c4d2e5"
down_revision: Union[str, None] = "42d3f0ad1b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ranking_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pool_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("count_10", sa.Integer(), nullable=False),
        sa.Column("count_7", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["pool_id"], ["pools.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pool_id", "match_id", "user_id", name="uq_ranking_snapshot_pool_match_user"),
    )
    op.create_index(
        "ix_ranking_snapshots_pool_user",
        "ranking_snapshots",
        ["pool_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ranking_snapshots_pool_user", table_name="ranking_snapshots")
    op.drop_table("ranking_snapshots")
