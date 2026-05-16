import time
import httpx
from app.config import settings

_token: str | None = None
_token_expires: float = 0


async def _get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expires
    if _token and time.time() < _token_expires - 60:
        return _token
    resp = await client.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": settings.igdb_client_id,
            "client_secret": settings.igdb_client_secret,
            "grant_type": "client_credentials",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    tok: str = data["access_token"]
    _token = tok
    _token_expires = time.time() + data["expires_in"]
    return tok


async def _post(client: httpx.AsyncClient, endpoint: str, query: str) -> list[dict]:
    token = await _get_token(client)
    resp = await client.post(
        f"https://api.igdb.com/v4/{endpoint}",
        headers={
            "Client-ID": settings.igdb_client_id,
            "Authorization": f"Bearer {token}",
        },
        content=query,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_top_games(client: httpx.AsyncClient, limit: int = 500, offset: int = 0) -> list[dict]:
    query = f"""
fields id, name, summary, storyline, first_release_date, total_rating, total_rating_count,
       genres.id, genres.name, genres.slug,
       platforms.id, platforms.name, platforms.slug,
       game_modes.id, game_modes.name, game_modes.slug,
       themes.id, themes.name, themes.slug,
       keywords.name,
       involved_companies.company.name, involved_companies.developer,
       cover.image_id,
       external_games.category, external_games.uid,
       websites.url,
       updated_at;
sort total_rating_count desc;
where total_rating_count > 50 & category = null;
limit {min(limit, 500)};
offset {offset};
"""
    return await _post(client, "games", query)


async def fetch_recent_games(client: httpx.AsyncClient, since_ts: int, offset: int = 0) -> list[dict]:
    query = f"""
fields id, name, summary, storyline, first_release_date, total_rating, total_rating_count,
       genres.id, genres.name, genres.slug,
       platforms.id, platforms.name, platforms.slug,
       game_modes.id, game_modes.name, game_modes.slug,
       themes.id, themes.name, themes.slug,
       keywords.name,
       involved_companies.company.name, involved_companies.developer,
       cover.image_id,
       external_games.category, external_games.uid,
       websites.url,
       updated_at;
where first_release_date > {since_ts}
      & total_rating_count > 10
      & total_rating > 65
      & category = null;
sort first_release_date desc;
limit 500;
offset {offset};
"""
    return await _post(client, "games", query)


async def fetch_upcoming_games(client: httpx.AsyncClient, until_ts: int, offset: int = 0) -> list[dict]:
    import time
    now_ts = int(time.time())
    query = f"""
fields id, name, summary, storyline, first_release_date, total_rating, total_rating_count,
       genres.id, genres.name, genres.slug,
       platforms.id, platforms.name, platforms.slug,
       game_modes.id, game_modes.name, game_modes.slug,
       themes.id, themes.name, themes.slug,
       keywords.name,
       involved_companies.company.name, involved_companies.developer,
       cover.image_id,
       external_games.category, external_games.uid,
       websites.url,
       updated_at;
where first_release_date > {now_ts}
      & first_release_date < {until_ts}
      & (hypes > 10 | follows > 50)
      & category = null;
sort hypes desc;
limit 500;
offset {offset};
"""
    return await _post(client, "games", query)


async def fetch_games_updated_since(client: httpx.AsyncClient, since_ts: int) -> list[dict]:
    query = f"""
fields id, name, summary, storyline, first_release_date, total_rating, total_rating_count,
       genres.id, genres.name, genres.slug,
       platforms.id, platforms.name, platforms.slug,
       game_modes.id, game_modes.name, game_modes.slug,
       themes.id, themes.name, themes.slug,
       keywords.name,
       involved_companies.company.name, involved_companies.developer,
       cover.image_id,
       external_games.category, external_games.uid,
       websites.url,
       updated_at;
where updated_at > {since_ts} & category = null;
limit 500;
"""
    return await _post(client, "games", query)


async def fetch_genres(client: httpx.AsyncClient) -> list[dict]:
    return await _post(client, "genres", "fields id, name, slug; limit 500;")


async def fetch_platforms(client: httpx.AsyncClient) -> list[dict]:
    return await _post(client, "platforms", "fields id, name, slug; limit 500;")


async def fetch_game_modes(client: httpx.AsyncClient) -> list[dict]:
    return await _post(client, "game_modes", "fields id, name, slug; limit 500;")


async def fetch_themes(client: httpx.AsyncClient) -> list[dict]:
    return await _post(client, "themes", "fields id, name, slug; limit 500;")
