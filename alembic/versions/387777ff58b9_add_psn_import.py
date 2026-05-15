"""add_psn_import

Revision ID: 387777ff58b9
Revises: 823ccafbabd3
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '387777ff58b9'
down_revision: Union[str, Sequence[str], None] = '823ccafbabd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column('psn_id', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_games_psn_id', 'games', ['psn_id'])
    op.create_index('idx_games_psn_id', 'games', ['psn_id'])

    op.add_column('users', sa.Column('psn_online_id', sa.String(32), nullable=True))
    op.create_unique_constraint('uq_users_psn_online_id', 'users', ['psn_online_id'])
    op.add_column('users', sa.Column('last_psn_sync_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_psn_sync_at')
    op.drop_constraint('uq_users_psn_online_id', 'users', type_='unique')
    op.drop_column('users', 'psn_online_id')

    op.drop_index('idx_games_psn_id', table_name='games')
    op.drop_constraint('uq_games_psn_id', 'games', type_='unique')
    op.drop_column('games', 'psn_id')
