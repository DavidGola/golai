"""PSN Library import — wrapper fin sur library_import_service.

L'adapter `PSNSource` implémente le Protocol LibraryImportSource.
"""

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.psn_import import PSNConfirmItem, PSNPreviewItem
from app.services.library_import import (
    ExternalOwnedGame,
    build_preview_generic,
    confirm_import_generic,
)
from app.sources import psn


class PSNSource:
    source_name = "psn"
    use_fuzzy_title_match = True  # PSN n'expose pas l'id Steam, fallback titre
    user_account_attr = "psn_online_id"
    user_sync_at_attr = "last_psn_sync_at"
    game_source_id_attr = "psn_id"

    async def resolve_account(self, raw_input: str) -> tuple[str, str]:
        # PSN : l'online_id user EST déjà l'identifiant d'API.
        return raw_input, raw_input

    async def fetch_owned(self, account_id: Any) -> list[ExternalOwnedGame]:
        npsso = settings.psn_npsso.get_secret_value()
        dtos = await asyncio.to_thread(psn.fetch_library, npsso, account_id)
        return [
            ExternalOwnedGame(
                source_id=dto.psn_id,
                title=dto.title,
                cover_url=dto.cover_url,
                completion_pct=dto.trophy_progress_pct,
                playtime_minutes=(
                    int(dto.hours_played * 60) if dto.hours_played is not None else None
                ),
                platforms=dto.platforms,
            )
            for dto in dtos
        ]

    def cast_source_id_for_db(self, source_id: str) -> str:
        return source_id  # Game.psn_id est String


psn_source = PSNSource()


async def build_preview(
    db: AsyncSession, user: User, online_id: str
) -> tuple[list[PSNPreviewItem], str]:
    """Fetch and match user's PSN library. Returns (items, online_id)."""
    internal_items, storage_value = await build_preview_generic(db, user, online_id, psn_source)
    items = [
        PSNPreviewItem(
            game_id=i.game.id,
            title=i.game.title,
            cover_url=i.game.cover_url,
            trophy_progress_pct=i.external.completion_pct,
            hours_played=(
                round(i.external.playtime_minutes / 60, 1)
                if i.external.playtime_minutes is not None
                else None
            ),
            suggested_status=i.suggested_status,
            already_in_library=i.already_in_library,
        )
        for i in internal_items
    ]
    return items, storage_value


async def confirm_import(
    db: AsyncSession, user: User, items: list[PSNConfirmItem], online_id: str
) -> tuple[int, int]:
    """Bulk-insert UserGame entries. Returns (imported, skipped) counts."""
    return await confirm_import_generic(
        db, user, items, psn_source,
        extract_hours_played=lambda item: item.hours_played,
        account_value=online_id,
    )
