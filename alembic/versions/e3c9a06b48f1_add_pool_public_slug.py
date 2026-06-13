"""add pool public_slug (unguessable public page url)

Revision ID: e3c9a06b48f1
Revises: d2b8c5e1f307
Create Date: 2026-06-13 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3c9a06b48f1"
down_revision: Union[str, None] = "d2b8c5e1f307"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pools", sa.Column("public_slug", sa.String(length=36), nullable=True))
    # Backfill existing rows with random UUIDs.
    op.execute("UPDATE pools SET public_slug = gen_random_uuid()::text WHERE public_slug IS NULL")
    op.alter_column("pools", "public_slug", nullable=False)
    op.create_unique_constraint("uq_pools_public_slug", "pools", ["public_slug"])


def downgrade() -> None:
    op.drop_constraint("uq_pools_public_slug", "pools", type_="unique")
    op.drop_column("pools", "public_slug")
