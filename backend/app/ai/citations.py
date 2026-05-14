import json
import re
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.store import CitedGame, StoreLink

_BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")
_SIMILARITY_THRESHOLD = 0.45

_CITATION_QUERY = text("""
    SELECT id, title, cover_url, steam_id
    FROM games
    WHERE title % :title
      AND similarity(title, :title) >= :threshold
    ORDER BY similarity(title, :title) DESC
    LIMIT 1
""")


def _extract_bold_titles(markdown: str) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for m in _BOLD_RE.finditer(markdown):
        raw = _YEAR_RE.sub("", m.group(1)).strip()
        if raw and raw not in seen:
            seen.add(raw)
            titles.append(raw)
    return titles


async def cite_games(db: AsyncSession, markdown: str) -> list[CitedGame]:
    titles = _extract_bold_titles(markdown)
    if not titles:
        return []

    seen_ids: set[uuid.UUID] = set()
    cited: list[CitedGame] = []

    for title in titles:
        row = (await db.execute(_CITATION_QUERY, {"title": title, "threshold": _SIMILARITY_THRESHOLD})).mappings().first()
        if row is None:
            continue
        game_id = uuid.UUID(str(row["id"]))
        if game_id in seen_ids:
            continue
        seen_ids.add(game_id)
        store_links: list[StoreLink] = []
        if row["steam_id"] is not None:
            store_links.append(StoreLink(
                platform="steam",
                url=f"https://store.steampowered.com/app/{row['steam_id']}/",
            ))
        cited.append(CitedGame(
            id=game_id,
            title=row["title"],
            cover_url=row["cover_url"],
            store_links=store_links,
        ))

    return cited


async def cited_games_sse_event(db: AsyncSession, markdown: str) -> tuple[str | None, list[dict] | None]:
    """
    Extrait les jeux cités, retourne (sse_line, cited_dicts).
    sse_line est None si aucun jeu trouvé.
    """
    cited = await cite_games(db, markdown)
    if not cited:
        return None, None
    cited_dicts = [g.model_dump(mode="json") for g in cited]
    sse = f"event: cited_games\ndata: {json.dumps({'games': cited_dicts})}\n\n"
    return sse, cited_dicts
