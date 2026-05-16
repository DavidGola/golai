import uuid
import pytest

from app.models.game import Game
from app.models.user_game import UserGameStatus
from app.schemas.user_game import UserGameCreate, UserGameUpdate
from app.services.user_games import add_to_library, list_library, remove_entry, update_entry


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


# ─── list_library : sort_by + limit + status filter ──────────────────────────


@pytest.fixture
async def three_games(db_session):
    games = [Game(title=f"Game {i}") for i in range(3)]
    db_session.add_all(games)
    await db_session.commit()
    for g in games:
        await db_session.refresh(g)
    return games


async def test_list_library_sort_by_playtime(db_session, user_a, three_games):
    g_low, g_high, g_none = three_games
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_low.id))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_high.id))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_none.id))

    # Set hours_played: low=5, high=42, none=NULL
    from sqlalchemy import select
    from app.models.user_game import UserGame
    entries = (await db_session.execute(select(UserGame))).scalars().all()
    by_game = {e.game_id: e for e in entries}
    by_game[g_low.id].hours_played = 5
    by_game[g_high.id].hours_played = 42
    await db_session.commit()

    result = await list_library(db_session, user_a.id, sort_by="playtime")
    # high (42) > low (5) > none (NULL last)
    assert [e.game_id for e in result] == [g_high.id, g_low.id, g_none.id]


async def test_list_library_sort_by_rating_nulls_last(db_session, user_a, three_games):
    g_low, g_high, g_none = three_games
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_low.id, user_rating=3))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_high.id, user_rating=9))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g_none.id))

    result = await list_library(db_session, user_a.id, sort_by="rating")
    assert [e.game_id for e in result] == [g_high.id, g_low.id, g_none.id]


async def test_list_library_default_sort_is_recent(db_session, user_a, three_games):
    """Comportement historique : sort par added_at desc — préservé pour le router."""
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.models.user_game import UserGame

    g1, g2, g3 = three_games
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g1.id))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g2.id))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g3.id))

    # Forcer des added_at distincts : la fixture savepoints fait que NOW()
    # retourne la même valeur dans la même transaction, donc on les écrase.
    base = datetime(2026, 1, 1)
    entries_by_game = {
        e.game_id: e for e in (await db_session.execute(select(UserGame))).scalars().all()
    }
    entries_by_game[g1.id].added_at = base
    entries_by_game[g2.id].added_at = base + timedelta(hours=1)
    entries_by_game[g3.id].added_at = base + timedelta(hours=2)
    await db_session.commit()

    result = await list_library(db_session, user_a.id)
    assert [e.game_id for e in result] == [g3.id, g2.id, g1.id]


async def test_list_library_limit(db_session, user_a, three_games):
    for g in three_games:
        await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g.id))

    result = await list_library(db_session, user_a.id, limit=2)
    assert len(result) == 2


async def test_list_library_status_filter(db_session, user_a, three_games):
    g1, g2, g3 = three_games
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g1.id, status=UserGameStatus.completed))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g2.id, status=UserGameStatus.todo))
    await add_to_library(db_session, user_a.id, UserGameCreate(game_id=g3.id, status=UserGameStatus.completed))

    result = await list_library(db_session, user_a.id, status=UserGameStatus.completed)
    assert {e.game_id for e in result} == {g1.id, g3.id}
