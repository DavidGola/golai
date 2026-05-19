"""
Reimport ciblé des éditions IGDB : remasters (9), remakes (8), expanded (10).

Usage (depuis la racine du projet) :
    python backend/scripts/ingest_editions.py

Ce que fait ce script :
  1. Fetche IGDB pour les catégories 8/9/10 uniquement
  2. Upserte les nouvelles entrées en DB (sans re-fetcher les jeux déjà présents)
  3. Résout les parent_game_id via le resolver Pass 2
  4. Génère les embeddings pour les nouveaux jeux

Ce que ce script ne fait PAS :
  - Re-fetch Steam/RAWG/SteamSpy sur les jeux existants
  - LLM batch steam_signals
  - Modifier les jeux déjà en DB (force=False)
"""
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.seed.embeddings import generate_embeddings
from app.seed.games import upsert_game
from app.services.igdb_edition_resolver import resolve_parent_links
from app.sources.igdb import fetch_editions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    total_inserted = 0
    total_resolved = 0

    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:
            offset = 0
            while True:
                logger.info("Fetching IGDB editions — offset %d ...", offset)
                games = await fetch_editions(client, offset)

                if not games:
                    logger.info("No more editions at offset %d — done.", offset)
                    break

                parent_links: dict[int, int] = {}
                for igdb_game in tqdm(games, desc=f"offset={offset}"):
                    try:
                        await upsert_game(session, client, igdb_game, force=False)
                        total_inserted += 1
                        parent_igdb_id = igdb_game.get("parent_game") or igdb_game.get("version_parent")
                        if parent_igdb_id:
                            parent_links[igdb_game["id"]] = parent_igdb_id
                    except Exception as exc:
                        logger.error("upsert failed — %s: %s", igdb_game.get("name", "?"), exc)
                        await session.rollback()

                if parent_links:
                    await resolve_parent_links(session, parent_links)
                    total_resolved += len(parent_links)

                await session.commit()
                offset += len(games)

    logger.info("Sync done — %d editions inserted, %d parent links resolved", total_inserted, total_resolved)

    logger.info("Generating embeddings for new games ...")
    async with AsyncSessionLocal() as session:
        model = SentenceTransformer("BAAI/bge-m3")
        count = await generate_embeddings(session, model)
        logger.info("%d embeddings generated", count)


if __name__ == "__main__":
    asyncio.run(main())
