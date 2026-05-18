"""
Script de mise à jour incrémentale de la base GolAi.

Stratégie :
  1. Jeux IGDB modifiés depuis le dernier sync (updated_at > last_sync)
  2. Refresh du steam_score pour tous les jeux avec steam_id
  3. Régénération des embeddings si le texte source a changé (via ingestion_hash)

Usage (depuis la racine du projet) :
    python backend/scripts/update.py
    python backend/scripts/update.py --scores-only
    python backend/scripts/update.py --no-embeddings
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import select
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.models.game import Game
from app.models.sync_state import SyncState
from app.seed.games import upsert_game
from app.sources import steam
from app.sources.igdb import fetch_games_updated_since

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SYNC_KEY = "igdb"


async def main(scores_only: bool, no_embeddings: bool) -> None:
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:

            # Load last sync state
            sync = (await session.execute(select(SyncState).where(SyncState.source == SYNC_KEY))).scalar_one_or_none()
            if sync is None:
                logger.error("No sync state found. Run seed.py first.")
                return

            last_sync_ts = int(sync.last_sync.timestamp())
            logger.info("Last sync: %s", sync.last_sync.isoformat())

            # Phase 1: New/modified IGDB games
            if not scores_only:
                logger.info("=== 1/3 Fetching IGDB updates since last sync ===")
                igdb_games = await fetch_games_updated_since(client, last_sync_ts)
                logger.info("Found %d updated/new games", len(igdb_games))

                for igdb_game in tqdm(igdb_games, desc="Updating"):
                    try:
                        await upsert_game(session, client, igdb_game)
                    except Exception as exc:
                        logger.error("[%s] Failed: %s", igdb_game.get("name", "?"), exc)

            # Phase 2: Refresh Steam scores
            logger.info("=== 2/3 Refreshing Steam scores ===")
            games_with_steam = (
                await session.execute(select(Game).where(Game.steam_id.is_not(None)))
            ).scalars().all()

            for game in tqdm(games_with_steam, desc="Steam scores"):
                try:
                    reviews = await steam.fetch_reviews(client, game.steam_id, num=100)  # type: ignore[arg-type]
                    if reviews:
                        if reviews["steam_score"] is not None:
                            game.steam_score = reviews["steam_score"]
                        if reviews["steam_total_reviews"] is not None:
                            game.steam_total_reviews = reviews["steam_total_reviews"]
                    await asyncio.sleep(0.2)
                except Exception as exc:
                    logger.warning("[%s] Steam refresh failed: %s", game.title, exc)

            await session.commit()
            logger.info("Steam scores refreshed")

            # Phase 3: Embeddings
            if not no_embeddings:
                logger.info("=== 3/3 Updating embeddings ===")
                from sentence_transformers import SentenceTransformer
                from app.seed.embeddings import generate_embeddings
                model = SentenceTransformer("BAAI/bge-m3")
                count = await generate_embeddings(session, model)
                logger.info("Embeddings updated: %d", count)

            # Update sync timestamp
            sync.last_sync = datetime.now(timezone.utc)
            await session.commit()
            logger.info("=== Update complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update GolAi database incrementally")
    parser.add_argument("--scores-only", action="store_true", help="Only refresh scores")
    parser.add_argument("--no-embeddings", action="store_true", help="Skip embedding regeneration")
    args = parser.parse_args()

    asyncio.run(main(
        scores_only=args.scores_only,
        no_embeddings=args.no_embeddings,
    ))
