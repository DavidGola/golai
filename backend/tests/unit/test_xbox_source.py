"""Unit tests for app/sources/xbox.py — httpx.get is mocked at the module boundary."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.sources.xbox import check_api_key, fetch_library, resolve_gamertag


def _mock_response(status_code: int) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    return r


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_valid_key_raises_nothing(mock_get):
    mock_get.return_value = _mock_response(200)
    check_api_key("valid-key")  # should not raise


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_401_raises_key_invalid(mock_get):
    mock_get.return_value = _mock_response(401)
    with pytest.raises(ValueError, match="xbox_api_key_invalid"):
        check_api_key("bad-key")


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_403_raises_key_invalid(mock_get):
    mock_get.return_value = _mock_response(403)
    with pytest.raises(ValueError, match="xbox_api_key_invalid"):
        check_api_key("bad-key")


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_429_raises_quota_exceeded(mock_get):
    mock_get.return_value = _mock_response(429)
    with pytest.raises(ValueError, match="xbox_quota_exceeded"):
        check_api_key("valid-key")


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_timeout_raises_unavailable(mock_get):
    mock_get.side_effect = httpx.TimeoutException("timeout")
    with pytest.raises(ValueError, match="xbox_api_unavailable"):
        check_api_key("valid-key")


@patch("app.sources.xbox.httpx.get")
def test_check_api_key_sends_authorization_header(mock_get):
    mock_get.return_value = _mock_response(200)
    check_api_key("my-api-key")
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["X-Authorization"] == "my-api-key"


# --- resolve_gamertag ---

def _gamertag_response(xuid: str = "2533274790395532", gamertag: str = "MajorNelson") -> MagicMock:
    r = _mock_response(200)
    r.json.return_value = {"content": {"profileUsers": [{"id": xuid, "gamertag": gamertag}]}}
    return r


@patch("app.sources.xbox.httpx.get")
def test_resolve_gamertag_valid_returns_xuid(mock_get):
    mock_get.return_value = _gamertag_response()
    xuid = resolve_gamertag("key", "MajorNelson")
    assert xuid == "2533274790395532"


@patch("app.sources.xbox.httpx.get")
def test_resolve_gamertag_not_found_raises(mock_get):
    mock_get.return_value = _mock_response(404)
    with pytest.raises(ValueError, match="xbox_invalid_gamertag"):
        resolve_gamertag("key", "NoSuchPlayer")


@patch("app.sources.xbox.httpx.get")
def test_resolve_gamertag_private_profile_raises(mock_get):
    mock_get.return_value = _mock_response(403)
    with pytest.raises(ValueError, match="xbox_profile_private"):
        resolve_gamertag("key", "PrivatePlayer")


# --- fetch_library ---

def _library_response(titles: list) -> MagicMock:
    r = _mock_response(200)
    r.json.return_value = {"content": {"titles": titles}}
    return r


def _title(
    title_id: str = "1095224633",
    name: str = "Halo Infinite",
    progress_pct: int = 15,
    image: str = "https://img.xbox.com/halo.jpg",
) -> dict:
    return {
        "titleId": title_id,
        "name": name,
        "type": "Game",
        "displayImage": image,
        "achievement": {
            "progressPercentage": progress_pct,
        },
    }


@patch("app.sources.xbox.httpx.get")
def test_fetch_library_returns_dtos(mock_get):
    mock_get.return_value = _library_response([_title()])
    dtos = fetch_library("key", "2533274790395532")
    assert len(dtos) == 1
    dto = dtos[0]
    assert dto.xbox_id == "1095224633"
    assert dto.title == "Halo Infinite"
    assert dto.cover_url == "https://img.xbox.com/halo.jpg"
    assert dto.achievement_progress_pct == 15


@patch("app.sources.xbox.httpx.get")
def test_fetch_library_empty_returns_empty_list(mock_get):
    mock_get.return_value = _library_response([])
    assert fetch_library("key", "2533274790395532") == []


@patch("app.sources.xbox.httpx.get")
def test_fetch_library_skips_non_game_titles(mock_get):
    app_title = {**_title(), "type": "App"}
    mock_get.return_value = _library_response([app_title])
    assert fetch_library("key", "2533274790395532") == []


@patch("app.sources.xbox.httpx.get")
def test_fetch_library_zero_progress_excluded(mock_get):
    mock_get.return_value = _library_response([_title(progress_pct=0)])
    assert fetch_library("key", "2533274790395532") == []
