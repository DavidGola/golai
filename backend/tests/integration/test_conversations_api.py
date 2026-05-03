import pytest_asyncio
from sqlalchemy import select

from app.models.conversation import Message


@pytest_asyncio.fixture
async def auth(user_factory):
    _, token = await user_factory()
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_auth(user_factory):
    _, token = await user_factory(email="other@test.fr", username="otheruser")
    return {"Authorization": f"Bearer {token}"}


async def test_conversations_crud(client, auth):
    r = await client.post("/conversations", json={"title": "Ma conv"}, headers=auth)
    assert r.status_code == 201
    conv_id = r.json()["id"]

    r2 = await client.get("/conversations", headers=auth)
    assert any(c["id"] == conv_id for c in r2.json())

    r3 = await client.patch(f"/conversations/{conv_id}", json={"title": "Renommée"}, headers=auth)
    assert r3.status_code == 200
    assert r3.json()["title"] == "Renommée"

    r4 = await client.delete(f"/conversations/{conv_id}", headers=auth)
    assert r4.status_code == 204

    r5 = await client.get("/conversations", headers=auth)
    assert not any(c["id"] == conv_id for c in r5.json())


async def test_get_conversation_wrong_owner_returns_404(client, auth, other_auth):
    r = await client.post("/conversations", json={"title": "Privée"}, headers=auth)
    conv_id = r.json()["id"]

    r2 = await client.get(f"/conversations/{conv_id}", headers=other_auth)
    assert r2.status_code == 404


async def test_patch_conversation_wrong_owner_returns_404(client, auth, other_auth):
    r = await client.post("/conversations", json={"title": "Privée"}, headers=auth)
    conv_id = r.json()["id"]

    r2 = await client.patch(f"/conversations/{conv_id}", json={"title": "Piratée"}, headers=other_auth)
    assert r2.status_code == 404


async def test_delete_cascades_messages(client, auth, session_factory, mock_stream_agent):
    r = await client.post("/conversations", json={"title": "À supprimer"}, headers=auth)
    conv_id = r.json()["id"]

    await client.post(
        f"/conversations/{conv_id}/messages",
        json={"content": "bonjour"},
        headers=auth,
    )

    r2 = await client.delete(f"/conversations/{conv_id}", headers=auth)
    assert r2.status_code == 204

    import uuid
    async with session_factory() as db:
        msgs = (await db.execute(
            select(Message).where(Message.conversation_id == uuid.UUID(conv_id))
        )).scalars().all()
    assert msgs == []
