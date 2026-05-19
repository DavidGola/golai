"""
Pass 2 de l'ingest IGDB : résolution des liens parent_game_id.

Appelé APRÈS que tous les Games d'une session sont insérés/upsertés (Pass 1).
Reçoit un dict {game_igdb_id: parent_igdb_id} et set parent_game_id sur chaque
Edition non-original dont le parent est présent en DB.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game

logger = logging.getLogger(__name__)


async def resolve_parent_links(
    db: AsyncSession,
    parent_links: dict[int, int],
) -> None:
    """Résout les liens Edition → Original en UUID locaux.

    Args:
        db: session SQLAlchemy active.
        parent_links: dict {child_igdb_id: parent_igdb_id} construit pendant Pass 1.
    """
    if not parent_links:
        return

    all_parent_igdb_ids = set(parent_links.values())
    result = await db.execute(
        select(Game.igdb_id, Game.id).where(Game.igdb_id.in_(all_parent_igdb_ids))
    )
    import uuid as _uuid
    igdb_to_uuid: dict[int, _uuid.UUID] = {row.igdb_id: row.id for row in result}

    for child_igdb_id, parent_igdb_id in parent_links.items():
        parent_uuid = igdb_to_uuid.get(parent_igdb_id)
        if parent_uuid is None:
            logger.debug(
                "parent IGDB %d not found in DB for child IGDB %d — orphan edition kept",
                parent_igdb_id,
                child_igdb_id,
            )
            continue

        child_result = await db.execute(
            select(Game).where(Game.igdb_id == child_igdb_id)
        )
        child = child_result.scalar_one_or_none()
        if child is not None:
            child.parent_game_id = parent_uuid

    await db.flush()
