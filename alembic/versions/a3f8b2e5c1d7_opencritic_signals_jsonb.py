"""opencritic_signals JSONB (ADR-0018 pattern application)

Migre les 2 colonnes plates `opencritic_score` + `opencritic_excerpts` vers
une seule colonne `opencritic_signals` JSONB. Établit le template formalisé
par ADR-0018 pour les futures sources catalogue.

Revision ID: a3f8b2e5c1d7
Revises: 101be584c190
Create Date: 2026-05-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3f8b2e5c1d7'
down_revision: Union[str, Sequence[str], None] = '101be584c190'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new JSONB column
    op.add_column(
        'games',
        sa.Column('opencritic_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. Migrate existing data (no-op si les colonnes sont vides en pratique,
    #    mais on écrit la SQL "comme si" pour servir de template aux migrations
    #    futures sur des sources qui contiennent des données).
    op.execute("""
        UPDATE games
        SET opencritic_signals = jsonb_strip_nulls(jsonb_build_object(
            'score', opencritic_score,
            'excerpts', CASE
                WHEN opencritic_excerpts IS NOT NULL THEN to_jsonb(opencritic_excerpts)
                ELSE NULL
            END
        ))
        WHERE opencritic_score IS NOT NULL OR opencritic_excerpts IS NOT NULL
    """)

    # 3. Drop old flat columns
    op.drop_column('games', 'opencritic_excerpts')
    op.drop_column('games', 'opencritic_score')


def downgrade() -> None:
    # 1. Recreate old flat columns
    op.add_column(
        'games',
        sa.Column('opencritic_score', sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        'games',
        sa.Column('opencritic_excerpts', postgresql.ARRAY(sa.Text()), nullable=True),
    )

    # 2. Reverse-migrate JSONB → flat columns
    op.execute("""
        UPDATE games
        SET
            opencritic_score = (opencritic_signals->>'score')::smallint,
            opencritic_excerpts = CASE
                WHEN opencritic_signals->'excerpts' IS NOT NULL
                THEN ARRAY(SELECT jsonb_array_elements_text(opencritic_signals->'excerpts'))
                ELSE NULL
            END
        WHERE opencritic_signals IS NOT NULL
    """)

    # 3. Drop the JSONB column
    op.drop_column('games', 'opencritic_signals')
