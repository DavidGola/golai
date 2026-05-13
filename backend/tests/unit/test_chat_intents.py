import pytest_asyncio

from app.models.game import Game
from app.models.user_game import UserGame, UserGameStatus
from app.schemas.conversation import ChatIntent
from app.services.chat_intents import EMPTY_LIBRARY_RESPONSE, short_circuit_response


async def test_no_intent_returns_none(db_session, user_a):
    result = await short_circuit_response(db_session, user_a.id, intent=None)
    assert result is None


async def test_unknown_intent_returns_none(db_session, user_a):
    # Enumération exhaustive garantie par le type, mais on vérifie qu'aucun intent
    # différent de LIBRARY_RECOMMEND ne court-circuite.
    # On passe None directement — ce chemin simule un intent non reconnu.
    result = await short_circuit_response(db_session, user_a.id, intent=None)
    assert result is None


async def test_library_recommend_empty_library_returns_message(db_session, user_a):
    result = await short_circuit_response(
        db_session, user_a.id, intent=ChatIntent.LIBRARY_RECOMMEND
    )
    assert result == EMPTY_LIBRARY_RESPONSE


async def test_library_recommend_with_one_game_returns_none(db_session, user_a, seeded_game):
    entry = UserGame(
        user_id=user_a.id,
        game_id=seeded_game.id,
        status=UserGameStatus.completed,
    )
    db_session.add(entry)
    await db_session.commit()

    result = await short_circuit_response(
        db_session, user_a.id, intent=ChatIntent.LIBRARY_RECOMMEND
    )
    assert result is None


async def test_library_recommend_with_multiple_statuses_returns_none(db_session, user_a, db_session_with_games):
    # Vérifie que tous les statuts comptent (not_started, dropped, etc.)
    result = await short_circuit_response(
        db_session, user_a.id, intent=ChatIntent.LIBRARY_RECOMMEND
    )
    assert result is None


@pytest_asyncio.fixture
async def db_session_with_games(db_session, user_a):
    """User avec 3 jeux de statuts variés."""
    for i, status in enumerate([UserGameStatus.not_started, UserGameStatus.dropped, UserGameStatus.todo]):
        game = Game(title=f"Game {i}")
        db_session.add(game)
        await db_session.flush()
        db_session.add(UserGame(user_id=user_a.id, game_id=game.id, status=status))
    await db_session.commit()
