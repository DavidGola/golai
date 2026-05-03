"""add_cache_tokens_to_messages

Revision ID: d2e8f1a4c9b3
Revises: c3f1a8b2e7d5
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e8f1a4c9b3'
down_revision: Union[str, None] = 'c3f1a8b2e7d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('cache_read_tokens', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('cache_write_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'cache_write_tokens')
    op.drop_column('messages', 'cache_read_tokens')
