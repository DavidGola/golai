import asyncio
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.user import User
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.xbox_import import XboxConfirmItem, XboxPreviewItem
from app.sources import xbox


def _suggest_status(pct: int | None) -> UserGameStatus | None:
    if pct is None:
        return None
    if pct == 100:
        return UserGameStatus.completed
    if pct > 0:
        return UserGameStatus.todo
    return UserGameStatus.not_started


async def build_preview(
    db: AsyncSession, user: User, gamertag: str
) -> list[XboxPreviewItem]:
    """Fetch and match user's Xbox library. Raises ValueError on error."""
    api_key = settings.openxbl_api_key.get_secret_value()
    xuid = await asyncio.to_thread(xbox.resolve_gamertag, api_key, gamertag)
    dtos = await asyncio.to_thread(xbox.fetch_library, api_key, xuid)

    user.xbox_gamertag = gamertag
    user.last_xbox_sync_at = datetime.now(UTC).replace(tzinfo=None)

    if not dtos:
        await db.commit()
        return []

    xbox_ids = [d.xbox_id for d in dtos]
    games_by_xbox_id: dict[str, Game] = {}

    rows = (await db.execute(
        select(Game).where(Game.xbox_id.in_(xbox_ids))
    )).scalars().all()
    for g in rows:
        if g.xbox_id:
            games_by_xbox_id[g.xbox_id] = g

    for dto in dtos:
        if dto.xbox_id in games_by_xbox_id:
            continue

        # Fuzzy title match via pg_trgm
        result = await db.execute(
            text(
                "SELECT id FROM games "
                "WHERE xbox_id IS NULL AND similarity(title, :title) >= 0.6 "
                "ORDER BY similarity(title, :title) DESC LIMIT 1"
            ),
            {"title": dto.title},
        )
        row = result.fetchone()
        if row:
            game = await db.get(Game, row[0])
            if game:
                games_by_xbox_id[dto.xbox_id] = game
                continue

        # Create minimal Game entry
        store_urls = {"xbox": dto.marketplace_url} if dto.marketplace_url else None
        game = Game(
            title=dto.title,
            cover_url=dto.cover_url,
            xbox_id=dto.xbox_id,
            store_urls=store_urls,
        )
        db.add(game)
        games_by_xbox_id[dto.xbox_id] = game

    await db.flush()

    existing_game_ids = set(
        (await db.execute(
            select(UserGame.game_id).where(UserGame.user_id == user.id)
        )).scalars().all()
    )

    items: list[XboxPreviewItem] = []
    for dto in dtos:
        game = games_by_xbox_id.get(dto.xbox_id)
        if game is None:
            continue
        items.append(XboxPreviewItem(
            game_id=game.id,
            title=game.title,
            cover_url=game.cover_url,
            achievement_progress_pct=dto.achievement_progress_pct,
            suggested_status=_suggest_status(dto.achievement_progress_pct),
            already_in_library=game.id in existing_game_ids,
        ))

    await db.commit()
    return items


async def confirm_import(
    db: AsyncSession, user: User, items: list[XboxConfirmItem]
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
            source="xbox",
        ))
        imported += 1

    user.last_xbox_sync_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return imported, skipped
