import logging

import httpx
from slugify import slugify
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.taxonomy import Criterion, GameMode, Genre, Platform, Tag
from app.sources import igdb

logger = logging.getLogger(__name__)

STATIC_CRITERIA = [
    {"slug": "story", "name": "Story"},
    {"slug": "gameplay", "name": "Gameplay"},
    {"slug": "graphics", "name": "Graphics"},
    {"slug": "replayability", "name": "Replayability"},
    {"slug": "atmosphere", "name": "Atmosphere"},
    {"slug": "difficulty", "name": "Difficulty"},
    {"slug": "length", "name": "Length"},
    {"slug": "multiplayer", "name": "Multiplayer"},
    {"slug": "music", "name": "Music"},
]


async def _upsert_all(session: AsyncSession, model, items: list[dict]) -> int:
    for item in items:
        slug = item.get("slug") or slugify(item["name"])
        stmt = (
            pg_insert(model)
            .values(slug=slug, name=item["name"])
            .on_conflict_do_update(index_elements=["slug"], set_={"name": item["name"]})
        )
        await session.execute(stmt)
    await session.commit()
    return len(items)


async def seed_taxonomy(session: AsyncSession, client: httpx.AsyncClient) -> None:
    logger.info("Seeding taxonomy from IGDB...")

    genres = await igdb.fetch_genres(client)
    n = await _upsert_all(session, Genre, genres)
    logger.info("  Genres: %d", n)

    modes = await igdb.fetch_game_modes(client)
    n = await _upsert_all(session, GameMode, modes)
    logger.info("  Game modes: %d", n)

    themes = await igdb.fetch_themes(client)
    n = await _upsert_all(session, Tag, themes)
    logger.info("  Tags (themes): %d", n)

    platforms = await igdb.fetch_platforms(client)
    n = await _upsert_all(session, Platform, platforms)
    logger.info("  Platforms: %d", n)

    for c in STATIC_CRITERIA:
        stmt = (
            pg_insert(Criterion)
            .values(**c)
            .on_conflict_do_nothing(index_elements=["slug"])
        )
        await session.execute(stmt)
    await session.commit()
    logger.info("  Criteria: %d (static)", len(STATIC_CRITERIA))
