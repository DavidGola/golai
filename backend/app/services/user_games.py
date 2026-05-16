import uuid
from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import Game
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.user_game import UserGameCreate, UserGameUpdate

LibrarySortBy = Literal["recent", "playtime", "rating"]


async def list_library(
    db: AsyncSession,
    user_id: uuid.UUID,
    status: UserGameStatus | None = None,
    *,
    sort_by: LibrarySortBy = "recent",
    limit: int | None = None,
) -> list[UserGame]:
    """
    Liste la Library d'un user.

    sort_by :
    - "recent"   : ajout descendant (defaut, comportement historique)
    - "playtime" : heures jouées desc, NULLs en dernier
    - "rating"   : note user desc, NULLs en dernier
    limit : nombre max d'entrées. None = pas de limite.
    """
    query = (
        select(UserGame)
        .options(selectinload(UserGame.game).options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
        ))
        .where(UserGame.user_id == user_id)
    )
    if status:
        query = query.where(UserGame.status == status)

    if sort_by == "playtime":
        query = query.order_by(desc(UserGame.hours_played).nulls_last())
    elif sort_by == "rating":
        query = query.order_by(desc(UserGame.user_rating).nulls_last())
    else:  # "recent"
        query = query.order_by(UserGame.added_at.desc())

    if limit is not None:
        query = query.limit(limit)

    return list((await db.execute(query)).scalars().all())


async def add_to_library(
    db: AsyncSession, user_id: uuid.UUID, payload: UserGameCreate
) -> UserGame:
    game = await db.get(Game, payload.game_id)
    if not game:
        raise ValueError("game_not_found")

    entry = UserGame(
        user_id=user_id,
        game_id=payload.game_id,
        status=payload.status,
        user_rating=payload.user_rating,
        review=payload.review,
        hours_played=payload.hours_played,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ValueError("already_in_library")
    await db.commit()

    result = await db.execute(
        select(UserGame)
        .options(selectinload(UserGame.game).options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
        ))
        .where(UserGame.id == entry.id)
    )
    return result.scalar_one()


async def update_entry(
    db: AsyncSession, user_id: uuid.UUID, ug_id: uuid.UUID, payload: UserGameUpdate
) -> UserGame | None:
    entry = await db.get(UserGame, ug_id)
    if not entry or entry.user_id != user_id:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()

    result = await db.execute(
        select(UserGame)
        .options(selectinload(UserGame.game).options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
        ))
        .where(UserGame.id == ug_id)
    )
    return result.scalar_one()


async def remove_entry(db: AsyncSession, user_id: uuid.UUID, ug_id: uuid.UUID) -> bool:
    entry = await db.get(UserGame, ug_id)
    if not entry or entry.user_id != user_id:
        return False
    await db.delete(entry)
    await db.commit()
    return True
