"""Integration tests for Xbox import routes — service is mocked."""
import uuid
from unittest.mock import patch

import pytest_asyncio

from app.models.user_game import UserGameStatus
from app.schemas.xbox_import import XboxPreviewItem


def _preview_item() -> XboxPreviewItem:
    return XboxPreviewItem(
        game_id=uuid.uuid4(),
        title="Halo Infinite",
        cover_url="https://img.xbox.com/halo.jpg",
        achievement_progress_pct=75,
        suggested_status=UserGameStatus.todo,
        already_in_library=False,
    )


@pytest_asyncio.fixture
async def user_headers(user_factory):
    _, token = await user_factory(email="xbox@test.fr", username="xboxuser")
    return {"Authorization": f"Bearer {token}"}


async def test_xbox_preview_requires_auth(client):
    r = await client.post("/users/me/games/xbox/preview", json={"gamertag": "MajorNelson"})
    assert r.status_code == 401


async def test_xbox_preview_invalid_gamertag_format(client, user_headers):
    r = await client.post(
        "/users/me/games/xbox/preview",
        json={"gamertag": ""},
        headers=user_headers,
    )
    assert r.status_code == 422


async def test_xbox_preview_unknown_gamertag_returns_404(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview") as mock:
        mock.side_effect = ValueError("xbox_invalid_gamertag")
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "NoSuchPlayer"},
            headers=user_headers,
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "xbox_invalid_gamertag"


async def test_xbox_preview_private_profile_returns_403(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview") as mock:
        mock.side_effect = ValueError("xbox_profile_private")
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "PrivatePlayer"},
            headers=user_headers,
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "xbox_profile_private"


async def test_xbox_preview_api_unavailable_returns_503(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview") as mock:
        mock.side_effect = ValueError("xbox_api_unavailable")
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "AnyPlayer"},
            headers=user_headers,
        )
    assert r.status_code == 503


async def test_xbox_preview_key_invalid_returns_503(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview") as mock:
        mock.side_effect = ValueError("xbox_api_key_invalid")
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "AnyPlayer"},
            headers=user_headers,
        )
    assert r.status_code == 503


async def test_xbox_preview_quota_exceeded_returns_429(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview") as mock:
        mock.side_effect = ValueError("xbox_quota_exceeded")
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "AnyPlayer"},
            headers=user_headers,
        )
    assert r.status_code == 429


async def test_xbox_preview_happy_path(client, user_headers):
    with patch("app.routers.user_games.xbox_service.build_preview", return_value=([_preview_item()], "MajorNelson")):
        r = await client.post(
            "/users/me/games/xbox/preview",
            json={"gamertag": "MajorNelson"},
            headers=user_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Halo Infinite"
    assert body["items"][0]["achievement_progress_pct"] == 75


async def test_xbox_import_requires_auth(client):
    r = await client.post("/users/me/games/xbox/import", json={"items": []})
    assert r.status_code == 401


async def test_xbox_import_happy_path(client, user_headers):
    game_id = str(uuid.uuid4())
    with patch("app.routers.user_games.xbox_service.confirm_import", return_value=(3, 0)):
        r = await client.post(
            "/users/me/games/xbox/import",
            json={
                "gamertag": "MajorNelson",
                "items": [{"game_id": game_id, "status": "completed", "user_rating": 9, "review": None}],
            },
            headers=user_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 3
    assert body["skipped"] == 0
