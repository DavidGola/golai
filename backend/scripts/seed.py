"""
Script de seed initial de la base GolAi.

Usage (depuis la racine du projet) :
    python backend/scripts/seed.py --limit 20 --with-steam-summary
    python backend/scripts/seed.py --limit 500 --with-steam-summary
    python backend/scripts/seed.py --limit 500 --no-steam-summary --skip-embeddings
    python backend/scripts/seed.py --limit 500 --resume  # reprend après crash
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
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.models.sync_state import SyncState
from app.seed.embeddings import generate_embeddings
from app.seed.games import upsert_game
from app.seed.taxonomy import seed_taxonomy
from app.sources.igdb import fetch_top_games

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(limit: int, skip_embeddings: bool, resume: bool, force: bool) -> None:
    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:

            # Step 1: Taxonomy
            logger.info("=== 1/3 Taxonomy ===")
            await seed_taxonomy(session, client)

            # Step 2: Games
            logger.info("=== 2/3 Games (limit=%d) ===", limit)

            offset = 0
            if resume:
                from sqlalchemy import func, select
                from app.models.game import Game
                result = await session.execute(select(func.count(Game.id)))
                offset = result.scalar() or 0
                logger.info("Resuming from offset %d", offset)

            total = 0
            for batch_start in range(offset, limit, 500):
                batch_limit = min(500, limit - batch_start)
                logger.info("Fetching IGDB games %d–%d...", batch_start, batch_start + batch_limit)

                igdb_games = await fetch_top_games(client, limit=batch_limit, offset=batch_start)
                if not igdb_games:
                    break

                for igdb_game in tqdm(igdb_games, desc="Games"):
                    try:
                        await upsert_game(session, client, igdb_game, force=force)
                        total += 1
                    except Exception as exc:
                        logger.error("[%s] Failed: %s", igdb_game.get("name", "?"), exc)
                        await session.rollback()

            logger.info("Games imported: %d", total)

            # Step 3: Embeddings
            if not skip_embeddings:
                logger.info("=== 3/3 Embeddings ===")
                logger.info("Loading BAAI/bge-m3 (first run: ~30s download)...")
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("BAAI/bge-m3")
                count = await generate_embeddings(session, model)
                logger.info("Embeddings generated: %d", count)

            # Record sync state
            from sqlalchemy import select as sa_select
            sync = (await session.execute(sa_select(SyncState).where(SyncState.source == "igdb"))).scalar_one_or_none()
            if sync is None:
                sync = SyncState(source="igdb", last_sync=datetime.now(timezone.utc))
                session.add(sync)
            else:
                sync.last_sync = datetime.now(timezone.utc)
            await session.commit()

            logger.info("=== Seed complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed GolAi database")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-fetch toutes les sources même pour les jeux déjà en base")
    args = parser.parse_args()

    asyncio.run(main(
        limit=args.limit,
        skip_embeddings=args.skip_embeddings,
        resume=args.resume,
        force=args.force,
    ))
