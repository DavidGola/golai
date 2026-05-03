from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.taxonomy import user_favorite_genres as ufg_table, user_important_criteria as uic_table
from app.models.user_game import UserGame, UserGameStatus
from app.services.users import (
    delete_user,
    set_favorite_genres,
    set_important_criteria,
)


async def test_set_favorite_genres_replaces(db_session, user_a, seeded_genres):
    g1, g2 = seeded_genres
    await set_favorite_genres(db_session, user_a.id, [g1.id, g2.id])
    await db_session.commit()

    rows = (await db_session.execute(
        select(ufg_table).where(ufg_table.c.user_id == user_a.id)
    )).fetchall()
    assert {r.genre_id for r in rows} == {g1.id, g2.id}

    await set_favorite_genres(db_session, user_a.id, [g2.id])
    await db_session.commit()

    rows = (await db_session.execute(
        select(ufg_table).where(ufg_table.c.user_id == user_a.id)
    )).fetchall()
    assert [r.genre_id for r in rows] == [g2.id]


async def test_set_favorite_genres_empty_clears(db_session, user_a, seeded_genres):
    g1, _ = seeded_genres
    await set_favorite_genres(db_session, user_a.id, [g1.id])
    await db_session.commit()

    await set_favorite_genres(db_session, user_a.id, [])
    await db_session.commit()

    rows = (await db_session.execute(
        select(ufg_table).where(ufg_table.c.user_id == user_a.id)
    )).fetchall()
    assert rows == []


async def test_set_important_criteria_replaces(db_session, user_a, seeded_criteria):
    c1, c2 = seeded_criteria
    await set_important_criteria(db_session, user_a.id, [c1.id, c2.id])
    await db_session.commit()

    await set_important_criteria(db_session, user_a.id, [c1.id])
    await db_session.commit()

    rows = (await db_session.execute(
        select(uic_table).where(uic_table.c.user_id == user_a.id)
    )).fetchall()
    assert [r.criterion_id for r in rows] == [c1.id]


async def test_delete_user_cascades(db_session, user_a, seeded_game, conversation_a):  # noqa: ARG001
    ug = UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.todo)
    db_session.add(ug)
    await db_session.commit()

    await delete_user(db_session, user_a)

    convs = (await db_session.execute(
        select(Conversation).where(Conversation.user_id == user_a.id)
    )).scalars().all()
    games = (await db_session.execute(
        select(UserGame).where(UserGame.user_id == user_a.id)
    )).scalars().all()
    assert convs == []
    assert games == []
