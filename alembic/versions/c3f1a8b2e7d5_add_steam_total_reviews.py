"""add_steam_total_reviews

Revision ID: c3f1a8b2e7d5
Revises: b7c1e3f9a2d4
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f1a8b2e7d5'
down_revision: Union[str, None] = 'b7c1e3f9a2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('steam_total_reviews', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('games', 'steam_total_reviews')
