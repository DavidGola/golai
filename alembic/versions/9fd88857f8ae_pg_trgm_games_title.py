"""pg_trgm_games_title

Revision ID: 9fd88857f8ae
Revises: c7edc7987d27
Create Date: 2026-05-11 20:57:25.156510

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9fd88857f8ae'
down_revision: Union[str, Sequence[str], None] = 'c7edc7987d27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX idx_games_title_trgm ON games USING gin (title gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_games_title_trgm")
