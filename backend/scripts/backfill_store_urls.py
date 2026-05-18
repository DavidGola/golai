"""
Backfill store_urls sur les jeux existants en base depuis IGDB external_games.

Usage (depuis la racine du projet) :
    python backend/scripts/backfill_store_urls.py
    python backend/scripts/backfill_store_urls.py --dry-run   # aperçu sans écriture
    python backend/scripts/backfill_store_urls.py --limit 100 # traite les 100 premiers

Réseau requis : appels IGDB API.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from app.models.game import Game
from app.seed.games import _extract_store_data
from app.sources.igdb import _post

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def fetch_external_games(client: httpx.AsyncClient, igdb_id: int) -> list[dict]:
    query = f"fields uid, url, category; where game = {igdb_id} & category = (1,5,11,13,26,36); limit 20;"
    return await _post(client, "external_games", query)


async def backfill(dry_run: bool, limit: int | None) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        async with AsyncSessionLocal() as session:
            stmt = select(Game.id, Game.igdb_id, Game.steam_id, Game.title).where(
                Game.igdb_id.is_not(None),
                Game.store_urls.is_(None),
            )
            if limit:
                stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).all()
            logger.info("Jeux à traiter : %d", len(rows))

            updated = 0
            for row in rows:
                try:
                    external_games = await fetch_external_games(client, row.igdb_id)
                    _, store_urls = _extract_store_data(external_games)
                    if row.steam_id and "steam" not in store_urls:
                        store_urls["steam"] = f"https://store.steampowered.com/app/{row.steam_id}/"
                    if not store_urls:
                        logger.debug("[%s] Aucun store trouvé", row.title)
                        continue
                    logger.info("[%s] Stores : %s", row.title, list(store_urls.keys()))
                    if not dry_run:
                        await session.execute(
                            update(Game).where(Game.id == row.id).values(store_urls=store_urls)
                        )
                        await session.commit()
                    updated += 1
                    await asyncio.sleep(0.25)
                except Exception as exc:
                    logger.warning("[%s] Erreur : %s", row.title, exc)

    logger.info("Terminé — %d jeux mis à jour (%s)", updated, "dry-run" if dry_run else "écriture")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(backfill(args.dry_run, args.limit))
