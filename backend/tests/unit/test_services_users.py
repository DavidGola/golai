from datetime import datetime, timezone

from sqlalchemy import select

from app.models.conversation import Conversation, Message, MessageRole
from app.models.message_proposal import MessageProposal, ProposalActionType
from app.models.rate_limit import RateLimitBucket
from app.models.taxonomy import (
    user_favorite_genres as ufg_table,
    user_important_criteria as uic_table,
)
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


async def test_delete_user_cascades(
    db_session, user_a, seeded_game, seeded_genres, seeded_criteria
):
    g1, _ = seeded_genres
    c1, _ = seeded_criteria

    # user_game
    ug = UserGame(user_id=user_a.id, game_id=seeded_game.id, status=UserGameStatus.todo)
    db_session.add(ug)

    # conversation → message → proposal
    conv = Conversation(user_id=user_a.id, title="cascade test")
    db_session.add(conv)
    await db_session.flush()

    msg = Message(conversation_id=conv.id, role=MessageRole.user, content="hello")
    db_session.add(msg)
    await db_session.flush()

    proposal = MessageProposal(
        message_id=msg.id,
        action_type=ProposalActionType.add_to_library,
        payload={"game_id": str(seeded_game.id)},
    )
    db_session.add(proposal)

    # taxonomie user
    await db_session.execute(
        ufg_table.insert().values(user_id=user_a.id, genre_id=g1.id)
    )
    await db_session.execute(
        uic_table.insert().values(user_id=user_a.id, criterion_id=c1.id)
    )

    now = datetime.now(tz=timezone.utc)
    auth_bucket = RateLimitBucket(
        bucket_key=f"chat:auth:{user_a.id}",
        scope="auth",
        window_start=now,
        request_count=5,
    )
    anon_bucket = RateLimitBucket(
        bucket_key="chat:anonymous:1.2.3.4",
        scope="anonymous",
        window_start=now,
        request_count=3,
    )
    db_session.add_all([auth_bucket, anon_bucket])
    await db_session.commit()

    user_id = user_a.id
    await delete_user(db_session, user_a)

    assert (await db_session.execute(
        select(Conversation).where(Conversation.user_id == user_id)
    )).scalars().all() == []

    assert (await db_session.execute(
        select(Message).where(Message.id == msg.id)
    )).scalars().all() == []

    assert (await db_session.execute(
        select(MessageProposal).where(MessageProposal.id == proposal.id)
    )).scalars().all() == []

    assert (await db_session.execute(
        select(UserGame).where(UserGame.user_id == user_id)
    )).scalars().all() == []

    assert (await db_session.execute(
        select(ufg_table).where(ufg_table.c.user_id == user_id)
    )).fetchall() == []

    assert (await db_session.execute(
        select(uic_table).where(uic_table.c.user_id == user_id)
    )).fetchall() == []

    assert (await db_session.execute(
        select(RateLimitBucket).where(
            RateLimitBucket.bucket_key == f"chat:auth:{user_id}"
        )
    )).scalars().all() == []

    # le bucket anonyme doit survivre
    surviving = (await db_session.execute(
        select(RateLimitBucket).where(
            RateLimitBucket.bucket_key == "chat:anonymous:1.2.3.4"
        )
    )).scalars().all()
    assert len(surviving) == 1
