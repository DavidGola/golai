import uuid

import pytest_asyncio

from app.models.game import Game


@pytest_asyncio.fixture
async def game(session_factory):
    async with session_factory() as db:
        g = Game(title="Portal 2")
        db.add(g)
        await db.commit()
        await db.refresh(g)
    return g


@pytest_asyncio.fixture
async def user_a(user_factory):
    _, token = await user_factory(email="a@test.fr", username="usera")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_b(user_factory):
    _, token = await user_factory(email="b@test.fr", username="userb")
    return {"Authorization": f"Bearer {token}"}


async def test_add_game_unknown_returns_404(client, user_a):
    r = await client.post(
        "/users/me/games",
        json={"game_id": str(uuid.uuid4())},
        headers=user_a,
    )
    assert r.status_code == 404


async def test_add_game_duplicate_returns_409(client, user_a, game):
    payload = {"game_id": str(game.id)}
    await client.post("/users/me/games", json=payload, headers=user_a)
    r = await client.post("/users/me/games", json=payload, headers=user_a)
    assert r.status_code == 409


async def test_add_game_happy_path(client, user_a, game):
    r = await client.post(
        "/users/me/games",
        json={"game_id": str(game.id), "status": "todo"},
        headers=user_a,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["game"]["title"] == "Portal 2"
    assert body["status"] == "todo"


async def test_list_library_filter_by_status(client, user_a, game):
    await client.post("/users/me/games", json={"game_id": str(game.id), "status": "todo"}, headers=user_a)

    r_all = await client.get("/users/me/games", headers=user_a)
    assert len(r_all.json()) == 1

    r_completed = await client.get("/users/me/games?status=completed", headers=user_a)
    assert len(r_completed.json()) == 0

    r_todo = await client.get("/users/me/games?status=todo", headers=user_a)
    assert len(r_todo.json()) == 1


async def test_patch_game_wrong_owner_returns_404(client, user_a, user_b, game):
    r = await client.post("/users/me/games", json={"game_id": str(game.id)}, headers=user_a)
    ug_id = r.json()["id"]

    r2 = await client.patch(f"/users/me/games/{ug_id}", json={"status": "completed"}, headers=user_b)
    assert r2.status_code == 404


async def test_delete_game_wrong_owner_returns_404(client, user_a, user_b, game):
    r = await client.post("/users/me/games", json={"game_id": str(game.id)}, headers=user_a)
    ug_id = r.json()["id"]

    r2 = await client.delete(f"/users/me/games/{ug_id}", headers=user_b)
    assert r2.status_code == 404

    r3 = await client.get("/users/me/games", headers=user_a)
    assert len(r3.json()) == 1
