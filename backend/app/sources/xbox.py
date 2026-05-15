"""Xbox source — thin wrapper around OpenXBL REST API isolating the dependency."""
from dataclasses import dataclass

import httpx

_BASE = "https://xbl.io/api/v2"
_HEALTH_URL = f"{_BASE}/account"
_SEARCH_URL = f"{_BASE}/friends/search"
_ACHIEVEMENTS_URL = f"{_BASE}/achievements/player"


@dataclass
class XboxGameDTO:
    xbox_id: str
    title: str
    cover_url: str | None
    achievement_progress_pct: int | None
    marketplace_url: str | None


def _headers(api_key: str) -> dict:
    return {"X-Authorization": api_key}


def _get(url: str, api_key: str, **kwargs) -> httpx.Response:
    try:
        return httpx.get(url, headers=_headers(api_key), timeout=10, **kwargs)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise ValueError("xbox_api_unavailable") from exc


def _check_status(response: httpx.Response) -> None:
    if response.status_code in (401,):
        raise ValueError("xbox_api_key_invalid")
    if response.status_code == 403:
        raise ValueError("xbox_profile_private")
    if response.status_code == 429:
        raise ValueError("xbox_quota_exceeded")
    if response.status_code >= 500:
        raise ValueError("xbox_api_unavailable")


def check_api_key(api_key: str) -> None:
    """Validate the OpenXBL API key with a lightweight GET.

    Raises ValueError: xbox_api_key_invalid | xbox_quota_exceeded | xbox_api_unavailable
    """
    response = _get(_HEALTH_URL, api_key)
    if response.status_code in (401, 403):
        raise ValueError("xbox_api_key_invalid")
    if response.status_code == 429:
        raise ValueError("xbox_quota_exceeded")
    if response.status_code >= 500:
        raise ValueError("xbox_api_unavailable")


def resolve_gamertag(api_key: str, gamertag: str) -> str:
    """Resolve a gamertag to an Xbox User ID (XUID).

    Raises ValueError: xbox_invalid_gamertag | xbox_profile_private | xbox_api_key_invalid | xbox_quota_exceeded | xbox_api_unavailable
    """
    response = _get(_SEARCH_URL, api_key, params={"gt": gamertag})
    if response.status_code == 404:
        raise ValueError("xbox_invalid_gamertag")
    _check_status(response)

    users = response.json().get("content", {}).get("profileUsers", [])
    if not users:
        raise ValueError("xbox_invalid_gamertag")
    return users[0]["id"]


def fetch_library(api_key: str, xuid: str) -> list[XboxGameDTO]:
    """Fetch a user's Xbox achievement titles (= played games with ≥1 achievement).

    Raises ValueError: xbox_profile_private | xbox_api_key_invalid | xbox_quota_exceeded | xbox_api_unavailable
    """
    response = _get(f"{_ACHIEVEMENTS_URL}/{xuid}", api_key)
    _check_status(response)

    titles = response.json().get("content", {}).get("titles", [])
    result: list[XboxGameDTO] = []
    for t in titles:
        if t.get("type") != "Game":
            continue
        achievement = t.get("achievement") or {}
        pct = achievement.get("progressPercentage")
        if not pct:
            continue
        result.append(XboxGameDTO(
            xbox_id=str(t["titleId"]),
            title=t["name"],
            cover_url=t.get("displayImage"),
            achievement_progress_pct=int(pct) if pct is not None else None,
            marketplace_url=None,
        ))
    return result
