from datetime import datetime, UTC

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.user import User
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.steam_import import SteamConfirmItem, SteamPreviewItem
from app.sources import steam


async def build_preview(
    db: AsyncSession, user: User, raw_input: str
) -> list[SteamPreviewItem]:
    """Fetch and match the user's Steam library. Raises ValueError on bad input or private profile."""
    async with httpx.AsyncClient() as client:
        steamid64 = await steam.resolve_steam_input(client, raw_input, settings.steam_api_key)
        if steamid64 is None:
            if steam._extract_input(raw_input) is None:
                raise ValueError("steam_invalid_input")
            raise ValueError("steam_profile_private")

        raw_games = await steam.fetch_owned_games(client, steamid64, settings.steam_api_key)

    if raw_games is None:
        raise ValueError("steam_profile_private")

    if not raw_games:
        user.steam_id = steamid64
        user.last_steam_sync_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
        return []

    appids = [g["appid"] for g in raw_games]
    rows = (await db.execute(select(Game).where(Game.steam_id.in_(appids)))).scalars().all()
    game_by_appid: dict[int, Game] = {g.steam_id: g for g in rows if g.steam_id is not None}

    # Create minimal Game entries for appids not yet in the catalog.
    for raw in raw_games:
        if raw["appid"] in game_by_appid:
            continue
        game = Game(
            title=raw["name"],
            steam_id=raw["appid"],
            cover_url=raw["cover_url"],
        )
        db.add(game)
        game_by_appid[raw["appid"]] = game

    await db.flush()

    # Detect games already in this user's library.
    existing_game_ids = set(
        (await db.execute(
            select(UserGame.game_id).where(UserGame.user_id == user.id)
        )).scalars().all()
    )

    preview_items: list[SteamPreviewItem] = []
    for raw in raw_games:
        game = game_by_appid.get(raw["appid"])
        if game is None:
            continue

        playtime = raw["playtime_forever"]
        hours = round(playtime / 60, 1) if playtime > 0 else None
        suggested = UserGameStatus.not_started if playtime == 0 else None

        preview_items.append(SteamPreviewItem(
            game_id=game.id,
            title=game.title,
            cover_url=game.cover_url,
            hours_on_record=hours,
            suggested_status=suggested,
            already_in_library=game.id in existing_game_ids,
        ))

    user.steam_id = steamid64
    user.last_steam_sync_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return preview_items


async def confirm_import(
    db: AsyncSession, user: User, items: list[SteamConfirmItem]
) -> tuple[int, int]:
    """Bulk-insert UserGame entries. Returns (imported, skipped) counts."""
    if not items:
        return 0, 0

    game_ids = [item.game_id for item in items]
    existing = set(
        (await db.execute(
            select(UserGame.game_id)
            .where(UserGame.user_id == user.id)
            .where(UserGame.game_id.in_(game_ids))
        )).scalars().all()
    )

    imported = 0
    skipped = 0
    for item in items:
        if item.game_id in existing:
            skipped += 1
            continue
        db.add(UserGame(
            user_id=user.id,
            game_id=item.game_id,
            status=item.status,
            user_rating=item.user_rating,
            review=item.review,
            hours_played=item.hours_on_record,
            source="steam",
        ))
        imported += 1

    await db.commit()
    return imported, skipped
