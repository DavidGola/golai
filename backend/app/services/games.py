import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import Game
from app.models.taxonomy import Genre, GameMode, Platform, Tag


async def list_games(
    db: AsyncSession,
    q: str | None = None,
    genre_slug: str | None = None,
    platform_slug: str | None = None,
    mode_slug: str | None = None,
    tag_slug: str | None = None,
    min_rating: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Game], int]:
    query = (
        select(Game)
        .options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
        )
        .distinct()
    )

    if q:
        query = query.where(Game.title.ilike(f"%{q}%"))
    if genre_slug:
        query = query.join(Game.genres).where(Genre.slug == genre_slug)
    if platform_slug:
        query = query.join(Game.platforms).where(Platform.slug == platform_slug)
    if mode_slug:
        query = query.join(Game.modes).where(GameMode.slug == mode_slug)
    if tag_slug:
        query = query.join(Game.tags).where(Tag.slug == tag_slug)
    if min_rating is not None:
        query = query.where(Game.igdb_rating >= min_rating)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Game.igdb_rating.desc().nulls_last()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(query)).scalars().all()

    return list(rows), total


async def get_game(db: AsyncSession, game_id: uuid.UUID) -> Game | None:
    result = await db.execute(
        select(Game)
        .options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
            selectinload(Game.modes),
            selectinload(Game.tags),
        )
        .where(Game.id == game_id)
    )
    return result.scalar_one_or_none()
