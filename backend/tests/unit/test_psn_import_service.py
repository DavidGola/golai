"""Unit tests for app/services/psn_import.py — sources.psn.fetch_library is mocked."""
from unittest.mock import patch

import pytest

from app.models.game import Game
from app.models.user_game import UserGame, UserGameStatus
from app.services.psn_import import build_preview, confirm_import
from app.sources.psn import PSNGameDTO


def _dto(
    psn_id: str = "NPWR001",
    title: str = "God of War",
    cover_url: str | None = "https://img/gow.jpg",
    trophy_progress_pct: int | None = 75,
    hours_played: float | None = 10.0,
) -> PSNGameDTO:
    return PSNGameDTO(
        psn_id=psn_id,
        title=title,
        cover_url=cover_url,
        trophy_progress_pct=trophy_progress_pct,
        hours_played=hours_played,
    )


@pytest.mark.asyncio
async def test_build_preview_empty_library_updates_sync_at(db_session, user_a):
    with patch("app.services.psn_import.psn.fetch_library", return_value=[]):
        result = await build_preview(db_session, user_a, "SomeUser")

    assert result == []
    assert user_a.last_psn_sync_at is not None
    assert user_a.psn_online_id == "SomeUser"


@pytest.mark.asyncio
async def test_build_preview_psn_id_exact_match(db_session, user_a):
    game = Game(title="God of War", psn_id="NPWR001")
    db_session.add(game)
    await db_session.commit()

    with patch("app.services.psn_import.psn.fetch_library", return_value=[_dto()]):
        result = await build_preview(db_session, user_a, "SomeUser")

    assert len(result) == 1
    item = result[0]
    assert item.game_id == game.id
    assert item.title == "God of War"
    assert item.already_in_library is False
    assert item.trophy_progress_pct == 75
    assert item.hours_played == 10.0


@pytest.mark.asyncio
async def test_build_preview_fuzzy_title_match(db_session, user_a):
    # Game with no psn_id but title similar enough (>= 0.6 similarity)
    game = Game(title="God of War")
    db_session.add(game)
    await db_session.commit()

    with patch("app.services.psn_import.psn.fetch_library", return_value=[_dto()]):
        result = await build_preview(db_session, user_a, "SomeUser")

    assert len(result) == 1
    assert result[0].game_id == game.id


@pytest.mark.asyncio
async def test_build_preview_new_game_created(db_session, user_a):
    with patch("app.services.psn_import.psn.fetch_library", return_value=[_dto(title="Unknown PSN Title")]):
        result = await build_preview(db_session, user_a, "SomeUser")

    assert len(result) == 1
    # Game should have been created with the psn_id
    from sqlalchemy import select
    from app.models.game import Game as GameModel
    game = (await db_session.execute(
        select(GameModel).where(GameModel.psn_id == "NPWR001")
    )).scalar_one()
    assert game.title == "Unknown PSN Title"


@pytest.mark.asyncio
async def test_build_preview_already_in_library(db_session, user_a):
    game = Game(title="God of War", psn_id="NPWR001")
    db_session.add(game)
    await db_session.flush()
    ug = UserGame(user_id=user_a.id, game_id=game.id, status=UserGameStatus.completed)
    db_session.add(ug)
    await db_session.commit()

    with patch("app.services.psn_import.psn.fetch_library", return_value=[_dto()]):
        result = await build_preview(db_session, user_a, "SomeUser")

    assert result[0].already_in_library is True


@pytest.mark.asyncio
async def test_build_preview_suggested_status_from_trophy_pct(db_session, user_a):
    dtos = [
        _dto(psn_id="NPWR001", title="Game100", trophy_progress_pct=100),
        _dto(psn_id="NPWR002", title="Game50", trophy_progress_pct=50),
        _dto(psn_id="NPWR003", title="Game0", trophy_progress_pct=0),
    ]
    with patch("app.services.psn_import.psn.fetch_library", return_value=dtos):
        result = await build_preview(db_session, user_a, "SomeUser")

    by_psn = {item.title: item for item in result}
    assert by_psn["Game100"].suggested_status == UserGameStatus.completed
    assert by_psn["Game50"].suggested_status == UserGameStatus.todo
    assert by_psn["Game0"].suggested_status == UserGameStatus.not_started


@pytest.mark.asyncio
async def test_confirm_import_inserts_with_psn_source_and_updates_sync_at(db_session, user_a):
    game = Game(title="God of War", psn_id="NPWR001")
    db_session.add(game)
    await db_session.flush()

    from app.schemas.psn_import import PSNConfirmItem
    item = PSNConfirmItem(game_id=game.id, status=UserGameStatus.completed, user_rating=9, review=None, hours_played=20.0)

    imported, skipped = await confirm_import(db_session, user_a, [item])

    assert imported == 1
    assert skipped == 0
    assert user_a.last_psn_sync_at is not None

    from sqlalchemy import select
    ug = (await db_session.execute(
        select(UserGame).where(UserGame.user_id == user_a.id).where(UserGame.game_id == game.id)
    )).scalar_one()
    assert ug.source == "psn"
    assert ug.hours_played == 20.0


@pytest.mark.asyncio
async def test_confirm_import_idempotent_second_call_all_skipped(db_session, user_a):
    game = Game(title="Spider-Man", psn_id="NPWR002")
    db_session.add(game)
    await db_session.flush()

    from app.schemas.psn_import import PSNConfirmItem
    item = PSNConfirmItem(game_id=game.id, status=None, user_rating=None, review=None, hours_played=None)

    imported1, skipped1 = await confirm_import(db_session, user_a, [item])
    imported2, skipped2 = await confirm_import(db_session, user_a, [item])

    assert imported1 == 1
    assert skipped1 == 0
    assert imported2 == 0
    assert skipped2 == 1
