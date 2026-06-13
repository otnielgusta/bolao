"""add pool prediction visibility setting

Revision ID: 42d3f0ad1b8c
Revises: ec9f0e23c909
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "42d3f0ad1b8c"
down_revision: Union[str, None] = "ec9f0e23c909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pools",
        sa.Column(
            "show_predictions_before_deadline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("pools", "show_predictions_before_deadline")
