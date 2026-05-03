import logging
import re

import httpx

logger = logging.getLogger(__name__)

_STEAMID64_RE = re.compile(r"^\d{17}$")
_VANITY_RE = re.compile(r"^[\w-]{2,32}$")

_RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/"
_GET_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"


def _extract_input(raw: str) -> tuple[str, str] | None:
    """Parse raw input into ("steamid64", value) or ("vanity", value). Returns None if invalid."""
    s = raw.strip().rstrip("/")
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^www\.", "", s)

    m = re.match(r"^steamcommunity\.com/profiles/(\d{17})", s)
    if m:
        return ("steamid64", m.group(1))

    m = re.match(r"^steamcommunity\.com/id/([\w-]{2,32})", s)
    if m:
        return ("vanity", m.group(1))

    if _STEAMID64_RE.match(s):
        return ("steamid64", s)

    if _VANITY_RE.match(s):
        return ("vanity", s)

    return None


async def resolve_steam_input(
    client: httpx.AsyncClient, raw: str, api_key: str
) -> str | None:
    """Resolve any Steam profile input to a SteamID64 string. Returns None if invalid."""
    parsed = _extract_input(raw)
    if parsed is None:
        return None

    kind, value = parsed
    if kind == "steamid64":
        return value

    try:
        resp = await client.get(
            _RESOLVE_VANITY_URL,
            params={"key": api_key, "vanityurl": value},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Steam ResolveVanityURL failed for %r: %s", value, exc)
        return None

    data = resp.json().get("response", {})
    if data.get("success") != 1:
        return None
    return data["steamid"]


async def fetch_owned_games(
    client: httpx.AsyncClient, steamid64: str, api_key: str
) -> list[dict] | None:
    """Fetch owned games via IPlayerService/GetOwnedGames.

    Returns list of {appid, name, playtime_forever, cover_url} or None if private/error.
    """
    try:
        resp = await client.get(
            _GET_OWNED_GAMES_URL,
            params={
                "key": api_key,
                "steamid": steamid64,
                "include_appinfo": 1,
                "include_played_free_games": 1,
            },
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Steam GetOwnedGames failed for %s: %s", steamid64, exc)
        return None

    games = resp.json().get("response", {}).get("games")
    if games is None:
        return None

    return [
        {
            "appid": g["appid"],
            "name": g.get("name", f"Game {g['appid']}"),
            "playtime_forever": g.get("playtime_forever", 0),
            "cover_url": f"https://cdn.akamai.steamstatic.com/steam/apps/{g['appid']}/capsule_184x69.jpg",
        }
        for g in games
    ]


async def fetch_app_details(client: httpx.AsyncClient, steam_id: int) -> dict | None:
    try:
        resp = await client.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": steam_id, "l": "english"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Steam appdetails failed for %d: %s", steam_id, exc)
        return None

    data = resp.json().get(str(steam_id), {})
    if not data.get("success"):
        return None

    info = data["data"]
    description = info.get("short_description") or ""
    return {"steam_description": description or None}


async def fetch_reviews(client: httpx.AsyncClient, steam_id: int, num: int = 50) -> dict | None:
    try:
        resp = await client.get(
            f"https://store.steampowered.com/appreviews/{steam_id}",
            params={"json": 1, "filter": "recent", "num_per_page": num, "language": "all"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Steam reviews failed for %d: %s", steam_id, exc)
        return None

    data = resp.json()
    if data.get("success") != 1:
        return None

    summary = data.get("query_summary", {})
    total_positive = summary.get("total_positive", 0)
    total_reviews = summary.get("total_reviews", 0)
    score = round(total_positive / total_reviews * 100) if total_reviews > 0 else None

    reviews = data.get("reviews", [])
    texts = [r["review"] for r in reviews if r.get("review")]

    return {
        "steam_score": score,
        "steam_total_reviews": total_reviews if total_reviews > 0 else None,
        "review_texts": texts,
    }
