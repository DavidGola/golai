from sqlalchemy import select

from app.models.conversation import Message, MessageRole
from app.schemas.conversation import ChatIntent
from app.services.chat import stream_reply
from app.services.chat_intents import EMPTY_LIBRARY_RESPONSE
from app.services.conversations import append_message


async def test_stream_reply_persists_both_messages(db_session, user_a, conversation_a, mock_stream_agent):
    chunks = [c async for c in stream_reply(db_session, user_a, conversation_a, "Je veux un RPG")]

    token_events = [c for c in chunks if c.startswith("event: token")]
    done_events = [c for c in chunks if c.startswith("event: done")]
    assert len(token_events) == 2
    assert len(done_events) == 1

    msgs = (await db_session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_a.id)
        .order_by(Message.created_at)
    )).scalars().all()
    assert len(msgs) == 2
    assert msgs[0].role == MessageRole.user
    assert msgs[0].content == "Je veux un RPG"
    assert msgs[1].role == MessageRole.assistant
    assert msgs[1].content == "hello world"
    assert msgs[1].tokens_used == 42


async def test_stream_reply_error_no_assistant_message(db_session, user_a, conversation_a, mock_stream_agent_error):
    chunks = [c async for c in stream_reply(db_session, user_a, conversation_a, "question")]

    error_events = [c for c in chunks if c.startswith("event: error")]
    assert len(error_events) == 1

    msgs = (await db_session.execute(
        select(Message).where(Message.conversation_id == conversation_a.id)
    )).scalars().all()
    assert len(msgs) == 1
    assert msgs[0].role == MessageRole.user


async def test_stream_reply_empty_library_short_circuit_persists_zero_tokens(
    db_session, user_a, conversation_a, monkeypatch
):
    agent_called = False

    async def fake_stream(*args, **kwargs):
        nonlocal agent_called
        agent_called = True
        yield {"event": "token", "data": "unreachable"}

    monkeypatch.setattr("app.services.chat.stream_agent", fake_stream)

    chunks = [
        c async for c in stream_reply(
            db_session,
            user_a,
            conversation_a,
            "Selon mes préférences, recommande-moi 5 jeux",
            intent=ChatIntent.LIBRARY_RECOMMEND,
        )
    ]

    assert any("event: token" in c for c in chunks)
    assert any('"tokens_used": 0' in c for c in chunks)
    assert not agent_called

    msgs = (await db_session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_a.id)
        .order_by(Message.created_at)
    )).scalars().all()
    assert len(msgs) == 2
    assert msgs[1].role == MessageRole.assistant
    assert msgs[1].content == EMPTY_LIBRARY_RESPONSE
    assert msgs[1].tokens_used == 0


async def test_stream_reply_passes_history(db_session, user_a, conversation_a, monkeypatch):
    received_history = []

    async def spy_stream(deps, user_message, history):
        received_history.extend(history)
        yield {"event": "token", "data": "ok"}
        import json
        yield {"event": "done", "data": json.dumps({"usage": {"total_tokens": 1, "input_tokens": 1, "output_tokens": 0}})}

    monkeypatch.setattr("app.services.chat.stream_agent", spy_stream)

    await append_message(db_session, conversation_a.id, MessageRole.user, "msg1")
    await append_message(db_session, conversation_a.id, MessageRole.assistant, "reply1")
    await append_message(db_session, conversation_a.id, MessageRole.user, "msg2")

    _ = [c async for c in stream_reply(db_session, user_a, conversation_a, "nouvelle question")]

    # Les 3 messages précédents doivent être dans l'historique passé à stream_agent
    assert len(received_history) == 3
