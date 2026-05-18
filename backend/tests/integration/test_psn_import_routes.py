"""Integration tests for PSN import routes — service is mocked."""
from unittest.mock import patch
import uuid

import pytest_asyncio

from app.models.user_game import UserGameStatus
from app.schemas.psn_import import PSNPreviewItem


def _preview_item() -> PSNPreviewItem:
    return PSNPreviewItem(
        game_id=uuid.uuid4(),
        title="God of War",
        cover_url="https://img/gow.jpg",
        trophy_progress_pct=75,
        hours_played=10.0,
        suggested_status=UserGameStatus.todo,
        already_in_library=False,
    )


@pytest_asyncio.fixture
async def user_headers(user_factory):
    _, token = await user_factory(email="psn@test.fr", username="psnuser")
    return {"Authorization": f"Bearer {token}"}


async def test_psn_preview_requires_auth(client):
    r = await client.post("/users/me/games/psn/preview", json={"online_id": "VaultTec"})
    assert r.status_code == 401


async def test_psn_preview_invalid_online_id_format(client, user_headers):
    r = await client.post(
        "/users/me/games/psn/preview",
        json={"online_id": "ab"},  # too short (< 3 chars)
        headers=user_headers,
    )
    assert r.status_code == 422


async def test_psn_preview_private_profile_returns_403(client, user_headers):
    with patch("app.routers.user_games.psn_service.build_preview") as mock:
        mock.side_effect = ValueError("psn_profile_private")
        r = await client.post(
            "/users/me/games/psn/preview",
            json={"online_id": "PrivateUser"},
            headers=user_headers,
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "psn_profile_private"


async def test_psn_preview_npsso_expired_returns_503(client, user_headers):
    with patch("app.routers.user_games.psn_service.build_preview") as mock:
        mock.side_effect = ValueError("psn_npsso_invalid")
        r = await client.post(
            "/users/me/games/psn/preview",
            json={"online_id": "AnyUser"},
            headers=user_headers,
        )
    assert r.status_code == 503
    assert r.json()["detail"] == "psn_npsso_invalid"


async def test_psn_preview_happy_path(client, user_headers):
    items = [_preview_item()]
    with patch("app.routers.user_games.psn_service.build_preview", return_value=(items, "VaultTec")):
        r = await client.post(
            "/users/me/games/psn/preview",
            json={"online_id": "VaultTec"},
            headers=user_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "God of War"
    assert body["items"][0]["trophy_progress_pct"] == 75
    assert body["items"][0]["hours_played"] == 10.0


async def test_psn_import_requires_auth(client):
    r = await client.post("/users/me/games/psn/import", json={"items": []})
    assert r.status_code == 401


async def test_psn_import_happy_path(client, user_headers):
    game_id = str(uuid.uuid4())
    with patch("app.routers.user_games.psn_service.confirm_import", return_value=(2, 0)) as mock:
        r = await client.post(
            "/users/me/games/psn/import",
            json={
                "online_id": "VaultTec",
                "items": [
                    {"game_id": game_id, "status": "completed", "user_rating": 9, "review": None, "hours_played": 20.0},
                ],
            },
            headers=user_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0
    mock.assert_called_once()


async def test_psn_import_dedup_second_call_returns_skipped(client, user_headers):
    game_id = str(uuid.uuid4())
    with patch("app.routers.user_games.psn_service.confirm_import", return_value=(0, 1)):
        r = await client.post(
            "/users/me/games/psn/import",
            json={
                "online_id": "VaultTec",
                "items": [{"game_id": game_id, "status": None, "user_rating": None, "review": None, "hours_played": None}],
            },
            headers=user_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 0
    assert body["skipped"] == 1
