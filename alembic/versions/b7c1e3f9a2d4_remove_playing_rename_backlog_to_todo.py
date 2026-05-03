"""remove playing rename backlog to todo

Revision ID: b7c1e3f9a2d4
Revises: f4b2e9a1c7d3
Create Date: 2026-04-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c1e3f9a2d4"
down_revision: Union[str, None] = "f4b2e9a1c7d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_games ALTER COLUMN status TYPE VARCHAR(16)")

    op.execute("UPDATE user_games SET status = NULL WHERE status = 'playing'")
    op.execute("UPDATE user_games SET status = 'todo' WHERE status = 'backlog'")

    op.execute("DROP TYPE IF EXISTS user_game_status")
    op.execute(
        "CREATE TYPE user_game_status AS ENUM ('completed', 'todo', 'dropped', 'not_started')"
    )
    op.execute(
        "ALTER TABLE user_games ALTER COLUMN status TYPE user_game_status "
        "USING status::user_game_status"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_games ALTER COLUMN status TYPE VARCHAR(16)")

    op.execute("UPDATE user_games SET status = 'backlog' WHERE status = 'todo'")

    op.execute("DROP TYPE IF EXISTS user_game_status")
    op.execute(
        "CREATE TYPE user_game_status AS ENUM "
        "('playing', 'completed', 'backlog', 'dropped', 'not_started')"
    )
    op.execute(
        "ALTER TABLE user_games ALTER COLUMN status TYPE user_game_status "
        "USING status::user_game_status"
    )
