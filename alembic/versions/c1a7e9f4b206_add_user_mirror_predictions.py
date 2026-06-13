"""add user mirror predictions setting

Revision ID: c1a7e9f4b206
Revises: b8f3a1c4d2e5
Create Date: 2026-06-13 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a7e9f4b206"
down_revision: Union[str, None] = "b8f3a1c4d2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mirror_predictions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "mirror_predictions")
