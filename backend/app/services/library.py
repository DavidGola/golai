import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MIN_PLAYED_HOURS = 2.0


async def played_game_ids(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Retourne les Game IDs à exclure pour la découverte (Library Entries 'jouées', hors Backlog)."""
    result = await db.execute(
        text(
            "SELECT game_id FROM user_games"
            " WHERE user_id = :uid"
            " AND (status IN ('completed', 'dropped') OR hours_played >= :min)"
        ),
        {"uid": user_id, "min": MIN_PLAYED_HOURS},
    )
    return {row.game_id for row in result}
