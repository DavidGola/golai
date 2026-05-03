import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def search_game(client: httpx.AsyncClient, title: str, year: int | None = None) -> dict | None:
    params: dict = {
        "key": settings.rawg_api_key,
        "search": title,
        "page_size": 3,
        "search_precise": "true",
    }
    if year:
        params["dates"] = f"{year - 1}-01-01,{year + 1}-12-31"

    try:
        resp = await client.get("https://api.rawg.io/api/games", params=params, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("RAWG request failed for %r: %s", title, exc)
        return None

    results = resp.json().get("results", [])
    if not results:
        return None

    game = results[0]
    return {
        "rawg_id": game["id"],
        "metacritic_score": game.get("metacritic"),
    }
