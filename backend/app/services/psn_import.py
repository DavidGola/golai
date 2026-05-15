import asyncio
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Game
from app.models.user import User
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.psn_import import PSNConfirmItem, PSNPreviewItem
from app.sources import psn


def _suggest_status(trophy_pct: int | None) -> UserGameStatus | None:
    if trophy_pct is None:
        return None
    if trophy_pct == 100:
        return UserGameStatus.completed
    if trophy_pct > 0:
        return UserGameStatus.todo
    return UserGameStatus.not_started


async def build_preview(
    db: AsyncSession, user: User, online_id: str
) -> list[PSNPreviewItem]:
    """Fetch and match user's PSN library. Raises ValueError on error."""
    npsso = settings.psn_npsso.get_secret_value()
    dtos = await asyncio.to_thread(psn.fetch_library, npsso, online_id)

    if not dtos:
        user.psn_online_id = online_id
        user.last_psn_sync_at = datetime.now(UTC).replace(tzinfo=None)
        await db.commit()
        return []

    psn_ids = [d.psn_id for d in dtos]
    games_by_psn_id: dict[str, Game] = {}

    rows = (await db.execute(
        select(Game).where(Game.psn_id.in_(psn_ids))
    )).scalars().all()
    for g in rows:
        if g.psn_id:
            games_by_psn_id[g.psn_id] = g

    for dto in dtos:
        if dto.psn_id in games_by_psn_id:
            continue

        # Fuzzy title match via pg_trgm
        result = await db.execute(
            text(
                "SELECT id FROM games "
                "WHERE psn_id IS NULL AND similarity(title, :title) >= 0.6 "
                "ORDER BY similarity(title, :title) DESC LIMIT 1"
            ),
            {"title": dto.title},
        )
        row = result.fetchone()
        if row:
            game = await db.get(Game, row[0])
            if game:
                games_by_psn_id[dto.psn_id] = game
                continue

        # Create minimal Game entry
        game = Game(title=dto.title, cover_url=dto.cover_url, psn_id=dto.psn_id)
        db.add(game)
        games_by_psn_id[dto.psn_id] = game

    await db.flush()

    existing_game_ids = set(
        (await db.execute(
            select(UserGame.game_id).where(UserGame.user_id == user.id)
        )).scalars().all()
    )

    items: list[PSNPreviewItem] = []
    for dto in dtos:
        game = games_by_psn_id.get(dto.psn_id)
        if game is None:
            continue
        items.append(PSNPreviewItem(
            game_id=game.id,
            title=game.title,
            cover_url=game.cover_url,
            trophy_progress_pct=dto.trophy_progress_pct,
            hours_played=dto.hours_played,
            suggested_status=_suggest_status(dto.trophy_progress_pct),
            already_in_library=game.id in existing_game_ids,
        ))

    user.psn_online_id = online_id
    user.last_psn_sync_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return items


async def confirm_import(
    db: AsyncSession, user: User, items: list[PSNConfirmItem]
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
            hours_played=item.hours_played,
            source="psn",
        ))
        imported += 1

    user.last_psn_sync_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return imported, skipped
