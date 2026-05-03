import uuid
import pytest

from app.models.user_game import UserGameStatus
from app.schemas.user_game import UserGameCreate, UserGameUpdate
from app.services.user_games import add_to_library, remove_entry, update_entry


async def test_add_unknown_game_raises(db_session, user_a):
    payload = UserGameCreate(game_id=uuid.uuid4())
    with pytest.raises(ValueError, match="game_not_found"):
        await add_to_library(db_session, user_a.id, payload)


async def test_add_duplicate_raises(db_session, user_a, seeded_game):
    payload = UserGameCreate(game_id=seeded_game.id)
    await add_to_library(db_session, user_a.id, payload)

    with pytest.raises(ValueError, match="already_in_library"):
        await add_to_library(db_session, user_a.id, payload)


async def test_add_happy_path(db_session, user_a, seeded_game):
    payload = UserGameCreate(game_id=seeded_game.id, status=UserGameStatus.todo)
    entry = await add_to_library(db_session, user_a.id, payload)

    assert entry.game_id == seeded_game.id
    assert entry.user_id == user_a.id
    assert entry.game.title == seeded_game.title


async def test_update_entry_wrong_owner_returns_none(db_session, user_a, user_b, seeded_game):
    payload = UserGameCreate(game_id=seeded_game.id)
    entry = await add_to_library(db_session, user_a.id, payload)

    result = await update_entry(db_session, user_b.id, entry.id, UserGameUpdate(status=UserGameStatus.completed))
    assert result is None


async def test_remove_entry_wrong_owner_returns_false(db_session, user_a, user_b, seeded_game):
    payload = UserGameCreate(game_id=seeded_game.id)
    entry = await add_to_library(db_session, user_a.id, payload)

    removed = await remove_entry(db_session, user_b.id, entry.id)
    assert removed is False

    still_there = await remove_entry(db_session, user_a.id, entry.id)
    assert still_there is True
