"""add_rate_limit_buckets

Revision ID: 9f7a2c6b4d1e
Revises: d2e8f1a4c9b3
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f7a2c6b4d1e"
down_revision: Union[str, None] = "d2e8f1a4c9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index(
        "ix_rate_limit_buckets_updated_at",
        "rate_limit_buckets",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_updated_at", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
