"""add security columns: user token_version, pool is_public

Revision ID: d2b8c5e1f307
Revises: c1a7e9f4b206
Create Date: 2026-06-13 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2b8c5e1f307"
down_revision: Union[str, None] = "c1a7e9f4b206"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pools",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pools", "is_public")
    op.drop_column("users", "token_version")
