"""Unit tests for app/services/xbox_import.py — sources.xbox is mocked."""
from unittest.mock import patch

import pytest

from app.models.game import Game
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.xbox_import import XboxConfirmItem
from app.services.xbox_import import build_preview, confirm_import
from app.sources.xbox import XboxGameDTO


def _dto(
    xbox_id: str = "1095224633",
    title: str = "Halo Infinite",
    cover_url: str | None = "https://img.xbox.com/halo.jpg",
    achievement_progress_pct: int | None = 75,
    marketplace_url: str | None = None,
) -> XboxGameDTO:
    return XboxGameDTO(
        xbox_id=xbox_id,
        title=title,
        cover_url=cover_url,
        achievement_progress_pct=achievement_progress_pct,
        marketplace_url=marketplace_url,
    )


@pytest.mark.asyncio
async def test_build_preview_empty_library_returns_empty_tuple(db_session, user_a):
    with patch("app.services.xbox_import.xbox.fetch_library", return_value=[]):
        with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-123"):
            items, gamertag = await build_preview(db_session, user_a, "MajorNelson")

    assert items == []
    assert gamertag == "MajorNelson"
    assert user_a.xbox_gamertag is None
    assert user_a.last_xbox_sync_at is None


@pytest.mark.asyncio
async def test_build_preview_xbox_id_exact_match(db_session, user_a):
    game = Game(title="Halo Infinite", xbox_id="1095224633")
    db_session.add(game)
    await db_session.commit()

    with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-1"):
        with patch("app.services.xbox_import.xbox.fetch_library", return_value=[_dto()]):
            items, _ = await build_preview(db_session, user_a, "MajorNelson")

    assert len(items) == 1
    assert items[0].game_id == game.id
    assert items[0].already_in_library is False
    assert items[0].achievement_progress_pct == 75


@pytest.mark.asyncio
async def test_build_preview_fuzzy_title_match(db_session, user_a):
    game = Game(title="Halo Infinite")
    db_session.add(game)
    await db_session.commit()

    with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-1"):
        with patch("app.services.xbox_import.xbox.fetch_library", return_value=[_dto()]):
            items, _ = await build_preview(db_session, user_a, "MajorNelson")

    assert len(items) == 1
    assert items[0].game_id == game.id


@pytest.mark.asyncio
async def test_build_preview_new_game_created(db_session, user_a):
    with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-1"):
        with patch("app.services.xbox_import.xbox.fetch_library", return_value=[_dto(title="Brand New Xbox Game")]):
            items, _ = await build_preview(db_session, user_a, "MajorNelson")

    assert len(items) == 1
    from sqlalchemy import select as sa_select
    game = (await db_session.execute(
        sa_select(Game).where(Game.xbox_id == "1095224633")
    )).scalar_one()
    assert game.title == "Brand New Xbox Game"


@pytest.mark.asyncio
async def test_build_preview_already_in_library(db_session, user_a):
    game = Game(title="Halo Infinite", xbox_id="1095224633")
    db_session.add(game)
    await db_session.flush()
    db_session.add(UserGame(user_id=user_a.id, game_id=game.id, status=UserGameStatus.completed))
    await db_session.commit()

    with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-1"):
        with patch("app.services.xbox_import.xbox.fetch_library", return_value=[_dto()]):
            items, _ = await build_preview(db_session, user_a, "MajorNelson")

    assert items[0].already_in_library is True


@pytest.mark.asyncio
async def test_build_preview_suggested_status_from_achievement_pct(db_session, user_a):
    dtos = [
        _dto(xbox_id="111", title="Game100", achievement_progress_pct=100),
        _dto(xbox_id="222", title="Game50", achievement_progress_pct=50),
        _dto(xbox_id="333", title="Game0", achievement_progress_pct=0),
    ]
    with patch("app.services.xbox_import.xbox.resolve_gamertag", return_value="xuid-1"):
        with patch("app.services.xbox_import.xbox.fetch_library", return_value=dtos):
            items, _ = await build_preview(db_session, user_a, "MajorNelson")

    by_title = {item.title: item for item in items}
    assert by_title["Game100"].suggested_status == UserGameStatus.completed
    assert by_title["Game50"].suggested_status == UserGameStatus.todo
    assert by_title["Game0"].suggested_status == UserGameStatus.not_started


@pytest.mark.asyncio
async def test_confirm_import_inserts_and_saves_account(db_session, user_a):
    game = Game(title="Halo Infinite", xbox_id="1095224633")
    db_session.add(game)
    await db_session.flush()

    item = XboxConfirmItem(game_id=game.id, status=UserGameStatus.completed, user_rating=9, review=None)
    imported, skipped = await confirm_import(db_session, user_a, [item], "MajorNelson")

    assert imported == 1
    assert skipped == 0
    assert user_a.xbox_gamertag == "MajorNelson"
    assert user_a.last_xbox_sync_at is not None

    from sqlalchemy import select as sa_select
    ug = (await db_session.execute(
        sa_select(UserGame).where(UserGame.user_id == user_a.id).where(UserGame.game_id == game.id)
    )).scalar_one()
    assert ug.source == "xbox"


@pytest.mark.asyncio
async def test_confirm_import_idempotent(db_session, user_a):
    game = Game(title="Halo Infinite", xbox_id="1095224633")
    db_session.add(game)
    await db_session.flush()

    item = XboxConfirmItem(game_id=game.id, status=None, user_rating=None, review=None)
    imported1, skipped1 = await confirm_import(db_session, user_a, [item], "MajorNelson")
    imported2, skipped2 = await confirm_import(db_session, user_a, [item], "MajorNelson")

    assert imported1 == 1 and skipped1 == 0
    assert imported2 == 0 and skipped2 == 1
