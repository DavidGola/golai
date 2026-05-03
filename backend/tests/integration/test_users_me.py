import pytest_asyncio


@pytest_asyncio.fixture
async def auth(user_factory):
    _, token = await user_factory()
    return {"Authorization": f"Bearer {token}"}


async def test_get_me_returns_profile(client, auth):
    r = await client.get("/users/me", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "testuser"
    assert "favorite_genres" in body
    assert "important_criteria" in body


async def test_patch_me_playtime(client, auth):
    r = await client.patch("/users/me", json={"preferred_playtime": "medium"}, headers=auth)
    assert r.status_code == 200

    r2 = await client.get("/users/me", headers=auth)
    assert r2.json()["preferred_playtime"] == "medium"


async def test_patch_me_password_and_relogin(client, user_factory):
    email = "patch@test.fr"
    await user_factory(email=email, username="patchuser")
    r = await client.post("/auth/jwt/login", data={"username": email, "password": "Password123!"})
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    await client.patch("/users/me", json={"password": "NewPass456!"}, headers=auth)

    r2 = await client.post("/auth/jwt/login", data={"username": email, "password": "NewPass456!"})
    assert r2.status_code == 200
    assert "access_token" in r2.json()

    r3 = await client.post("/auth/jwt/login", data={"username": email, "password": "Password123!"})
    assert r3.status_code == 400


async def test_delete_me(client, user_factory):
    email = "del@test.fr"
    _, token = await user_factory(email=email, username="deluser")
    auth = {"Authorization": f"Bearer {token}"}

    r = await client.delete("/users/me", headers=auth)
    assert r.status_code == 204

    r2 = await client.post("/auth/jwt/login", data={"username": email, "password": "Password123!"})
    assert r2.status_code == 400
