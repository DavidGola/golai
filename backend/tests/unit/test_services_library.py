from app.models.user_game import UserGame, UserGameStatus
from app.services.library import MIN_PLAYED_HOURS, played_game_ids


async def test_played_game_ids_empty_library(db_session, user_a):
    result = await played_game_ids(db_session, user_a.id)
    assert result == set()


async def test_played_game_ids_completed(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.completed))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id in result


async def test_played_game_ids_dropped(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.dropped))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id in result


async def test_played_game_ids_not_started_zero_hours_is_backlog(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.not_started, hours_played=0.0))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id not in result


async def test_played_game_ids_not_started_above_threshold(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.not_started, hours_played=5.0))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id in result


async def test_played_game_ids_todo_below_threshold_is_backlog(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.todo, hours_played=1.5))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id not in result


async def test_played_game_ids_todo_at_threshold(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.todo, hours_played=MIN_PLAYED_HOURS))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id in result


async def test_played_game_ids_completed_zero_hours(db_session, user_a, seeded_game):
    db_session.add(UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.completed, hours_played=0.0))
    await db_session.commit()
    result = await played_game_ids(db_session, user_a.id)
    assert seeded_game.id in result
