import json
import uuid
from datetime import datetime, timezone

import pytest_asyncio
from sqlalchemy import select

from app.config import settings
from app.models.conversation import Message
from app.models.rate_limit import RateLimitBucket
from app.services.rate_limits import current_hour


@pytest_asyncio.fixture
async def auth(user_factory):
    _, token = await user_factory()
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_auth(user_factory):
    _, token = await user_factory(email="other@test.fr", username="otheruser")
    return {"Authorization": f"Bearer {token}"}


async def test_sse_stream_events(client, auth, mock_stream_agent):
    r_conv = await client.post("/conversations", json={"title": "Chat"}, headers=auth)
    conv_id = r_conv.json()["id"]

    r = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "Je veux un RPG"},
        headers=auth,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    body = r.text
    assert "event: token" in body
    assert "event: done" in body

    done_line = next(l for l in body.splitlines() if l.startswith("data:") and "assistant_message_id" in l)
    done_data = json.loads(done_line[len("data: "):])
    assert "assistant_message_id" in done_data
    assert done_data["tokens_used"] == 42


async def test_sse_persists_messages(client, auth, session_factory, mock_stream_agent):
    r_conv = await client.post("/conversations", json={"title": "Persist"}, headers=auth)
    conv_id = r_conv.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "hello"},
        headers=auth,
    )

    r = await client.get(f"/conversations/{conv_id}", headers=auth)
    msgs = r.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["tokens_used"] == 42
    assert msgs[1]["content"] == "hello world"


async def test_sse_error_no_assistant_message(client, auth, session_factory, mock_stream_agent_error):
    r_conv = await client.post("/conversations", json={"title": "Error"}, headers=auth)
    conv_id = r_conv.json()["id"]

    r = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "question"},
        headers=auth,
    )
    assert "event: error" in r.text

    async with session_factory() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
        )).scalars().all()
    assert len(msgs) == 1
    assert msgs[0].role.value == "user"


async def test_sse_wrong_owner_returns_404(client, auth, other_auth, session_factory, mock_stream_agent):
    r_conv = await client.post("/conversations", json={"title": "Privée"}, headers=auth)
    conv_id = r_conv.json()["id"]

    r = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "question"},
        headers=other_auth,
    )
    assert r.status_code == 404

    async with session_factory() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
        )).scalars().all()
    assert msgs == []


async def test_sse_rate_limit_returns_429_before_persisting(
    client,
    user_factory,
    session_factory,
    monkeypatch,
    mock_stream_agent,
):
    monkeypatch.setattr(settings, "chat_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "chat_auth_rate_limit_per_hour", 1)
    suffix = uuid.uuid4().hex
    user_id, token = await user_factory(email=f"rl-{suffix}@test.fr", username=f"rl{suffix}")
    auth = {"Authorization": f"Bearer {token}"}
    r_conv = await client.post("/conversations", json={"title": "Rate limit"}, headers=auth)
    conv_id = r_conv.json()["id"]

    async with session_factory() as db:
        bucket = RateLimitBucket(
            bucket_key=f"chat:auth:{user_id}",
            scope="chat:auth",
            window_start=current_hour(datetime.now(timezone.utc)),
            request_count=1,
        )
        await db.merge(bucket)
        await db.commit()

    r = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "question"},
        headers=auth,
    )
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0

    async with session_factory() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
        )).scalars().all()
    assert msgs == []


async def test_intent_library_recommend_empty_library_short_circuits(
    client, auth, session_factory, monkeypatch
):
    """library vide + intent → réponse hardcodée, agent non appelé."""
    agent_called = False

    async def fake_stream(*args, **kwargs):
        nonlocal agent_called
        agent_called = True
        yield {"event": "token", "data": "unreachable"}

    monkeypatch.setattr("app.services.chat.stream_agent", fake_stream)

    r_conv = await client.post("/conversations", json={"title": "CTA"}, headers=auth)
    conv_id = r_conv.json()["id"]

    r = await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "Selon mes préférences, recommande-moi 5 jeux", "intent": "library_recommend"},
        headers=auth,
    )
    assert r.status_code == 200
    assert "event: token" in r.text
    assert "event: done" in r.text
    assert "bibliothèque est encore vide" in r.text
    assert not agent_called

    done_line = next(l for l in r.text.splitlines() if l.startswith("data:") and "assistant_message_id" in l)
    done_data = json.loads(done_line[len("data: "):])
    assert done_data["tokens_used"] == 0

    r_conv_detail = await client.get(f"/conversations/{conv_id}", headers=auth)
    msgs = r_conv_detail.json()["messages"]
    assert len(msgs) == 2
    assert msgs[1]["role"] == "assistant"
    assert "bibliothèque est encore vide" in msgs[1]["content"]
    assert msgs[1]["tokens_used"] == 0


async def test_anonymous_chat_rate_limit_returns_429(client, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "chat_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "chat_anonymous_rate_limit_per_hour", 1)

    async with session_factory() as db:
        bucket = RateLimitBucket(
            bucket_key="chat:anonymous:127.0.0.1",
            scope="chat:anonymous",
            window_start=current_hour(datetime.now(timezone.utc)),
            request_count=1,
        )
        await db.merge(bucket)
        await db.commit()

    r = await client.post("/chat/anonymous", json={"content": "question", "history": []})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
