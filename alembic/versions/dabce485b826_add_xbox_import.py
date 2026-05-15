"""add_xbox_import

Revision ID: dabce485b826
Revises: 387777ff58b9
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dabce485b826'
down_revision: Union[str, Sequence[str], None] = '387777ff58b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('xbox_id', sa.String(20), nullable=True))
    op.create_unique_constraint('uq_games_xbox_id', 'games', ['xbox_id'])
    op.create_index('idx_games_xbox_id', 'games', ['xbox_id'])

    op.add_column('users', sa.Column('xbox_gamertag', sa.String(15), nullable=True))
    op.create_unique_constraint('uq_users_xbox_gamertag', 'users', ['xbox_gamertag'])
    op.add_column('users', sa.Column('last_xbox_sync_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_xbox_sync_at')
    op.drop_constraint('uq_users_xbox_gamertag', 'users', type_='unique')
    op.drop_column('users', 'xbox_gamertag')

    op.drop_index('idx_games_xbox_id', table_name='games')
    op.drop_constraint('uq_games_xbox_id', 'games', type_='unique')
    op.drop_column('games', 'xbox_id')
