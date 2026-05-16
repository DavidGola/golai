import re
import logging
from slugify import slugify

import httpx

logger = logging.getLogger(__name__)

_OWNERS_RE = re.compile(r"([\d,]+)\s*\.\.\s*([\d,]+)")


def _parse_owners(owners_str: str) -> tuple[int | None, int | None]:
    m = _OWNERS_RE.search(owners_str)
    if not m:
        return None, None
    lo = int(m.group(1).replace(",", ""))
    hi = int(m.group(2).replace(",", ""))
    return lo, hi


async def fetch_appdetails(client: httpx.AsyncClient, appid: int) -> dict | None:
    try:
        resp = await client.get(
            "https://steamspy.com/api.php",
            params={"request": "appdetails", "appid": appid},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("SteamSpy fetch failed for appid %d: %s", appid, exc)
        return None

    if not data or data.get("appid") is None:
        return None

    raw_tags: dict = data.get("tags") or {}
    tags = [
        {"name": name, "slug": slugify(name), "vote_count": count}
        for name, count in raw_tags.items()
    ]

    owners_min, owners_max = _parse_owners(data.get("owners") or "")

    return {
        "tags": tags,
        "owners_min": owners_min,
        "owners_max": owners_max,
        "players_2weeks": data.get("players_2weeks"),
        "ccu": data.get("ccu"),
    }
