"""Xbox Library import — wrapper fin sur library_import_service.

L'adapter `XboxSource` implémente le Protocol LibraryImportSource.
"""

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.xbox_import import XboxConfirmItem, XboxPreviewItem
from app.services.library_import import (
    ExternalOwnedGame,
    build_preview_generic,
    confirm_import_generic,
)
from app.sources import xbox


class XboxSource:
    source_name = "xbox"
    use_fuzzy_title_match = True  # OpenXBL n'expose pas l'id Steam, fallback titre
    user_account_attr = "xbox_gamertag"
    user_sync_at_attr = "last_xbox_sync_at"
    game_source_id_attr = "xbox_id"

    async def resolve_account(self, raw_input: str) -> tuple[str, str]:
        # Xbox : on résout le gamertag en xuid (pour l'API), mais on stocke
        # le gamertag user-friendly (pour l'affichage et les futurs sync).
        api_key = settings.openxbl_api_key.get_secret_value()
        xuid = await asyncio.to_thread(xbox.resolve_gamertag, api_key, raw_input)
        return xuid, raw_input  # (api_id pour fetch, storage_value pour user.xbox_gamertag)

    async def fetch_owned(self, account_id: Any) -> list[ExternalOwnedGame]:
        api_key = settings.openxbl_api_key.get_secret_value()
        dtos = await asyncio.to_thread(xbox.fetch_library, api_key, account_id)
        return [
            ExternalOwnedGame(
                source_id=dto.xbox_id,
                title=dto.title,
                cover_url=dto.cover_url,
                completion_pct=dto.achievement_progress_pct,
                extra_store_url=dto.marketplace_url,
            )
            for dto in dtos
        ]

    def cast_source_id_for_db(self, source_id: str) -> str:
        return source_id  # Game.xbox_id est String


xbox_source = XboxSource()


async def build_preview(
    db: AsyncSession, user: User, gamertag: str
) -> list[XboxPreviewItem]:
    """Fetch and match user's Xbox library."""
    internal_items = await build_preview_generic(db, user, gamertag, xbox_source)
    return [
        XboxPreviewItem(
            game_id=i.game.id,
            title=i.game.title,
            cover_url=i.game.cover_url,
            achievement_progress_pct=i.external.completion_pct,
            suggested_status=i.suggested_status,
            already_in_library=i.already_in_library,
        )
        for i in internal_items
    ]


async def confirm_import(
    db: AsyncSession, user: User, items: list[XboxConfirmItem]
) -> tuple[int, int]:
    """Bulk-insert UserGame entries. Returns (imported, skipped) counts."""
    return await confirm_import_generic(
        db, user, items, xbox_source,
        extract_hours_played=lambda item: None,  # Xbox API ne fournit pas le playtime
    )
