import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from slugify import slugify
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.taxonomy import GameMode, Genre, Platform, SteamTag, Tag
from app.models.taxonomy import games_genres, games_modes, games_platforms, games_steam_tags, games_tags
from app.sources import hltb, rawg, steam, steamspy

_CACHE_DIR = Path(".cache/steam_reviews")

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


_IGDB_STORE_CATEGORY: dict[int, str] = {
    1: "steam",
    5: "gog",
    11: "xbox",
    13: "nintendo",
    26: "playstation",
    36: "epic",
}


def _extract_store_data(external_games: list) -> tuple[int | None, dict[str, str]]:
    """Retourne (steam_id, store_urls) depuis la liste external_games IGDB."""
    steam_id: int | None = None
    store_urls: dict[str, str] = {}
    for eg in external_games:
        category = eg.get("category")
        store_key = _IGDB_STORE_CATEGORY.get(category)
        if not store_key:
            continue
        url = eg.get("url")
        if url:
            store_urls[store_key] = url
        if category == 1:
            try:
                steam_id = int(eg["uid"])
            except (KeyError, ValueError):
                pass
    return steam_id, store_urls


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


async def _sync_steam_tags(
    session: AsyncSession,
    game_id: uuid.UUID,
    tags: list[dict],
) -> None:
    await session.execute(sa_delete(games_steam_tags).where(games_steam_tags.c.game_id == game_id))
    for tag in tags:
        tag_id = await _get_or_create_taxonomy(session, SteamTag, tag["slug"], tag["name"])
        await session.execute(
            games_steam_tags.insert().values(
                game_id=game_id, tag_id=tag_id, vote_count=tag.get("vote_count")
            )
        )


async def upsert_game(
    session: AsyncSession,
    client: httpx.AsyncClient,
    igdb_game: dict,
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
    _IGDB_CATEGORY_TO_EDITION = {8: "remake", 9: "remaster", 10: "expanded"}
    game.edition_type = _IGDB_CATEGORY_TO_EDITION.get(igdb_game.get("category") or 0, "original")
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

    steam_id, store_urls = _extract_store_data(igdb_game.get("external_games") or [])
    if not steam_id:
        steam_id = _extract_steam_id_from_websites(igdb_game.get("websites") or [])
        if steam_id and "steam" not in store_urls:
            store_urls["steam"] = f"https://store.steampowered.com/app/{steam_id}/"
    if steam_id:
        with session.no_autoflush:
            conflict = (await session.execute(
                select(Game.id).where(Game.steam_id == steam_id).where(Game.id != game.id)
            )).scalar_one_or_none()
        if not conflict:
            game.steam_id = steam_id
        else:
            logger.warning("[%s] Steam id %d already used, skipping", title, steam_id)
            store_urls.pop("steam", None)
    if store_urls:
        game.store_urls = store_urls

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

        if review_texts:
            genre_names = [g["name"] for g in (igdb_game.get("genres") or []) if g.get("name")]
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path = _CACHE_DIR / f"{game.id}.jsonl"
            cache_path.write_text(json.dumps({
                "game_id": str(game.id),
                "title": title,
                "genres": genre_names,
                "steam_score": game.steam_score,
                "steam_total_reviews": game.steam_total_reviews,
                "reviews": review_texts,
            }))

        try:
            spy = await steamspy.fetch_appdetails(client, game.steam_id)
            if spy:
                await _sync_steam_tags(session, game.id, spy["tags"])
                game.steam_owners_min = spy["owners_min"]
                game.steam_owners_max = spy["owners_max"]
                game.steam_players_2weeks = spy["players_2weeks"]
                game.steam_ccu = spy["ccu"]
                game.steam_metrics_updated_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning("[%s] SteamSpy error: %s", title, exc)
        await asyncio.sleep(1.0)

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

    if force:
        game.ingestion_hash = None

    await session.commit()
    return game
