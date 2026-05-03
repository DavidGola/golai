"""add_steam_import

Revision ID: f4b2e9a1c7d3
Revises: a9455454548f
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b2e9a1c7d3'
down_revision: Union[str, Sequence[str], None] = 'a9455454548f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE requires Postgres >= 12 to run inside a transaction.
    op.execute("ALTER TYPE user_game_status ADD VALUE IF NOT EXISTS 'not_started'")

    op.add_column('users', sa.Column('steam_id', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('last_steam_sync_at', sa.DateTime(), nullable=True))
    op.create_unique_constraint('uq_users_steam_id', 'users', ['steam_id'])

    op.add_column('user_games', sa.Column('source', sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column('user_games', 'source')

    op.drop_constraint('uq_users_steam_id', 'users', type_='unique')
    op.drop_column('users', 'last_steam_sync_at')
    op.drop_column('users', 'steam_id')

    # Note: Postgres does not support removing enum values.
    # To fully revert 'not_started', recreate the enum type manually.
