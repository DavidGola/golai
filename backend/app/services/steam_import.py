"""Steam Library import — wrapper fin sur library_import_service.

L'adapter `SteamSource` implémente le Protocol LibraryImportSource.
La logique d'orchestration partagée vit dans library_import.py.
"""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.steam_import import SteamConfirmItem, SteamPreviewItem
from app.services.library_import import (
    ExternalOwnedGame,
    build_preview_generic,
    confirm_import_generic,
)
from app.sources import steam


class SteamSource:
    source_name = "steam"
    use_fuzzy_title_match = False  # appid Steam est canonique, pas besoin
    user_account_attr = "steam_id"
    user_sync_at_attr = "last_steam_sync_at"
    game_source_id_attr = "steam_id"

    async def resolve_account(self, raw_input: str) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            steamid64 = await steam.resolve_steam_input(
                client, raw_input, settings.steam_api_key
            )
        if steamid64 is None:
            if steam._extract_input(raw_input) is None:
                raise ValueError("steam_invalid_input")
            raise ValueError("steam_profile_private")
        # Steam stocke le steamid64 (résolu) pour les futurs sync.
        return steamid64, steamid64

    async def fetch_owned(self, account_id: Any) -> list[ExternalOwnedGame]:
        async with httpx.AsyncClient() as client:
            raw_games = await steam.fetch_owned_games(
                client, account_id, settings.steam_api_key
            )
        if raw_games is None:
            raise ValueError("steam_profile_private")
        return [
            ExternalOwnedGame(
                source_id=str(g["appid"]),
                title=g["name"],
                cover_url=g["cover_url"],
                playtime_minutes=g["playtime_forever"],
            )
            for g in raw_games
        ]

    def cast_source_id_for_db(self, source_id: str) -> int:
        return int(source_id)  # Game.steam_id est Integer


steam_source = SteamSource()


async def build_preview(
    db: AsyncSession, user: User, raw_input: str
) -> tuple[list[SteamPreviewItem], str]:
    """Fetch and match the user's Steam library. Returns (items, resolved_steam_id)."""
    internal_items, storage_value = await build_preview_generic(db, user, raw_input, steam_source)
    items = [
        SteamPreviewItem(
            game_id=i.game.id,
            title=i.game.title,
            cover_url=i.game.cover_url,
            hours_on_record=(
                round(i.external.playtime_minutes / 60, 1)
                if i.external.playtime_minutes and i.external.playtime_minutes > 0
                else None
            ),
            suggested_status=i.suggested_status,
            already_in_library=i.already_in_library,
        )
        for i in internal_items
    ]
    return items, storage_value


async def confirm_import(
    db: AsyncSession, user: User, items: list[SteamConfirmItem], steam_id: str
) -> tuple[int, int]:
    """Bulk-insert UserGame entries. Returns (imported, skipped) counts."""
    return await confirm_import_generic(
        db, user, items, steam_source,
        extract_hours_played=lambda item: item.hours_on_record,
        account_value=steam_id,
    )
