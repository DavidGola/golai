import asyncio
import logging
import re
import uuid
from datetime import datetime

import httpx
from slugify import slugify
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.taxonomy import GameMode, Genre, Platform, Tag
from app.models.taxonomy import games_genres, games_modes, games_platforms, games_tags
from app.sources import hltb, rawg, steam, summarizer

logger = logging.getLogger(__name__)


def _cover_url(image_id: str | None) -> str | None:
    if not image_id:
        return None
    return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"


def _extract_developer(involved_companies: list) -> str | None:
    for ic in involved_companies:
        if ic.get("developer") and ic.get("company"):
            return ic["company"]["name"]
    return None


def _extract_steam_id(external_games: list) -> int | None:
    for eg in external_games:
        if eg.get("category") == 1:  # category 1 = Steam
            try:
                return int(eg["uid"])
            except (KeyError, ValueError):
                pass
    return None


def _extract_steam_id_from_websites(websites: list) -> int | None:
    for site in websites:
        m = re.search(r"store\.steampowered\.com/app/(\d+)", site.get("url", ""))
        if m:
            return int(m.group(1))
    return None


async def _get_or_create_taxonomy(session: AsyncSession, model, slug: str, name: str):
    stmt = (
        pg_insert(model)
        .values(slug=slug, name=name)
        .on_conflict_do_update(index_elements=["slug"], set_={"name": name})
        .returning(model.id)
    )
    result = await session.execute(stmt)
    row = result.fetchone()
    if row:
        return row[0]
    # Fallback: fetch
    obj = (await session.execute(select(model).where(model.slug == slug))).scalar_one()
    return obj.id


async def _sync_taxonomy(
    session: AsyncSession,
    junction,
    entity_col: str,
    model,
    game_id: uuid.UUID,
    items: list[dict],
) -> None:
    await session.execute(sa_delete(junction).where(junction.c.game_id == game_id))
    for item in items:
        slug = item.get("slug") or slugify(item["name"])
        entity_id = await _get_or_create_taxonomy(session, model, slug, item["name"])
        await session.execute(
            junction.insert().values(game_id=game_id, **{entity_col: entity_id})
        )


async def upsert_game(
    session: AsyncSession,
    client: httpx.AsyncClient,
    igdb_game: dict,
    with_steam_summary: bool = True,
    force: bool = False,
) -> Game:
    igdb_id: int = igdb_game["id"]
    title: str = igdb_game.get("name", "")

    stmt = select(Game).where(Game.igdb_id == igdb_id)
    game = (await session.execute(stmt)).scalar_one_or_none()
    already_exists = game is not None

    if game is None:
        game = Game(igdb_id=igdb_id)
        session.add(game)

    # Jeu déjà en base et pas de force → skip les appels API externes
    if already_exists and not force:
        return game

    # IGDB core fields
    game.title = title
    game.summary = igdb_game.get("summary")
    game.storyline = igdb_game.get("storyline")
    game.developer = _extract_developer(igdb_game.get("involved_companies") or [])
    cover = igdb_game.get("cover")
    game.cover_url = _cover_url(cover.get("image_id") if cover else None)
    game.igdb_rating = igdb_game.get("total_rating")
    game.igdb_rating_count = igdb_game.get("total_rating_count")

    release_ts = igdb_game.get("first_release_date")
    year = datetime.fromtimestamp(release_ts).year if release_ts else None
    if release_ts:
        game.release_date = datetime.fromtimestamp(release_ts)

    updated_ts = igdb_game.get("updated_at")
    if updated_ts:
        game.igdb_updated_at = datetime.fromtimestamp(updated_ts)

    kw = igdb_game.get("keywords") or []
    game.keywords = [k["name"] for k in kw if k.get("name")] or None

    steam_id = _extract_steam_id(igdb_game.get("external_games") or [])
    if not steam_id:
        steam_id = _extract_steam_id_from_websites(igdb_game.get("websites") or [])
    if steam_id:
        with session.no_autoflush:
            conflict = (await session.execute(
                select(Game.id).where(Game.steam_id == steam_id).where(Game.id != game.id)
            )).scalar_one_or_none()
        if not conflict:
            game.steam_id = steam_id
        else:
            logger.warning("[%s] Steam id %d already used, skipping", title, steam_id)

    # Flush to get game.id for junction tables
    await session.flush()

    # RAWG
    try:
        rawg_data = await rawg.search_game(client, title, year)
        if rawg_data:
            with session.no_autoflush:
                conflict = (await session.execute(
                    select(Game.id).where(Game.rawg_id == rawg_data["rawg_id"]).where(Game.id != game.id)
                )).scalar_one_or_none()
            if not conflict:
                game.rawg_id = rawg_data["rawg_id"]
                game.metacritic_score = rawg_data["metacritic_score"]
            else:
                logger.warning("[%s] RAWG id %d already used, skipping", title, rawg_data["rawg_id"])
    except Exception as exc:
        logger.warning("[%s] RAWG error: %s", title, exc)
    await asyncio.sleep(0.25)

    # Steam
    review_texts: list[str] = []
    if game.steam_id:
        try:
            details = await steam.fetch_app_details(client, game.steam_id)
            if details:
                game.steam_description = details["steam_description"]
        except Exception as exc:
            logger.warning("[%s] Steam details error: %s", title, exc)
        await asyncio.sleep(0.2)

        try:
            reviews = await steam.fetch_reviews(client, game.steam_id)
            if reviews:
                game.steam_score = reviews["steam_score"]
                game.steam_total_reviews = reviews["steam_total_reviews"]
                review_texts = reviews["review_texts"]
        except Exception as exc:
            logger.warning("[%s] Steam reviews error: %s", title, exc)
        await asyncio.sleep(0.2)

        if with_steam_summary and review_texts:
            genre_names = [g["name"] for g in (igdb_game.get("genres") or []) if g.get("name")]
            game.steam_reviews_summary = await summarizer.summarize_reviews(
                review_texts,
                title,
                genre_names,
                game.steam_score,
                game.steam_total_reviews,
            )

    # HLTB
    try:
        hltb_data = await hltb.search_game(title)
        if hltb_data:
            with session.no_autoflush:
                conflict = (await session.execute(
                    select(Game.id).where(Game.hltb_id == hltb_data["hltb_id"]).where(Game.id != game.id)
                )).scalar_one_or_none()
            if not conflict:
                game.hltb_id = hltb_data["hltb_id"]
                game.hltb_main = hltb_data["hltb_main"]
                game.hltb_extra = hltb_data["hltb_extra"]
                game.hltb_completionist = hltb_data["hltb_completionist"]
            else:
                logger.warning("[%s] HLTB id %d already used, skipping", title, hltb_data["hltb_id"])
    except Exception as exc:
        logger.warning("[%s] HLTB error: %s", title, exc)
    await asyncio.sleep(0.3)

    # Taxonomy M:N
    await _sync_taxonomy(session, games_genres, "genre_id", Genre, game.id, igdb_game.get("genres") or [])
    await _sync_taxonomy(session, games_platforms, "platform_id", Platform, game.id, igdb_game.get("platforms") or [])
    await _sync_taxonomy(session, games_modes, "mode_id", GameMode, game.id, igdb_game.get("game_modes") or [])
    await _sync_taxonomy(session, games_tags, "tag_id", Tag, game.id, igdb_game.get("themes") or [])

    await session.commit()
    return game
