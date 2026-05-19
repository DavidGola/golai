"""add_editions_to_games

Revision ID: e5a2b7c3f1d9
Revises: a3f8b2e5c1d7
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'e5a2b7c3f1d9'
down_revision: Union[str, Sequence[str], None] = 'a3f8b2e5c1d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('games', sa.Column(
        'parent_game_id',
        UUID(as_uuid=True),
        sa.ForeignKey('games.id'),
        nullable=True,
    ))
    op.create_index('idx_games_parent_game_id', 'games', ['parent_game_id'])
    op.add_column('games', sa.Column(
        'edition_type',
        sa.String(),
        nullable=False,
        server_default='original',
    ))


def downgrade() -> None:
    op.drop_column('games', 'edition_type')
    op.drop_index('idx_games_parent_game_id', table_name='games')
    op.drop_column('games', 'parent_game_id')
