import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_game import UserGame
from app.schemas.conversation import ChatIntent

LIBRARY_RECOMMEND_PROMPT = "Selon mes préférences, recommande-moi 5 jeux"

EMPTY_LIBRARY_RESPONSE = (
    "Je ne peux pas te recommander de jeux : ta bibliothèque est encore vide. "
    "Ajoute quelques jeux que tu as joués (terminés, en cours, abandonnés…) "
    "ou importe ta bibliothèque Steam, puis reviens me demander."
)


async def short_circuit_response(
    db: AsyncSession,
    user_id: uuid.UUID,
    intent: ChatIntent | None,
) -> str | None:
    """Renvoie une réponse hardcodée si l'intent doit court-circuiter le LLM ; sinon None."""
    if intent is not ChatIntent.LIBRARY_RECOMMEND:
        return None
    count = await db.scalar(
        select(func.count()).select_from(UserGame).where(UserGame.user_id == user_id)
    )
    if count == 0:
        return EMPTY_LIBRARY_RESPONSE
    return None
