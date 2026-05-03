async def test_register_returns_201(client):
    r = await client.post(
        "/auth/register",
        json={"email": "alice@test.fr", "password": "Password123!", "username": "alice"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@test.fr"
    assert body["username"] == "alice"
    assert "id" in body


async def test_login_returns_token(client):
    await client.post(
        "/auth/register",
        json={"email": "bob@test.fr", "password": "Password123!", "username": "bob"},
    )
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "bob@test.fr", "password": "Password123!"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


async def test_login_wrong_password_returns_400(client):
    await client.post(
        "/auth/register",
        json={"email": "carol@test.fr", "password": "Password123!", "username": "carol"},
    )
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "carol@test.fr", "password": "wrong"},
    )
    assert r.status_code == 400


async def test_protected_endpoint_without_token_returns_401(client):
    r = await client.get("/users/me")
    assert r.status_code == 401


async def test_protected_endpoint_with_token_returns_200(client, user_factory):
    _, token = await user_factory()
    r = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
