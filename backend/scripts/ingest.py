"""
Orchestrateur d'ingestion GolAi — RAG Data Enrichment.

Usage (depuis la racine du projet) :
    python backend/scripts/ingest.py --phase upcoming [--max-per-query N] [--force]
    python backend/scripts/ingest.py --phase recent   [--max-per-query N] [--force]
    python backend/scripts/ingest.py --phase top --force [--max-per-query N]

Phases :
  upcoming  Q3 — jeux non-sortis (hypes/follows > seuil, ~200-300 jeux)
  recent    Q2 — jeux 2022-2026 qualité (rating_count > 10 & rating > 65, ~1000-1500)
  top       Q1 — catalogue historique (rating_count > 50, ~10-15K) — requiert --force

Chaque phase : 1) sync IGDB+Steam+SteamSpy  2) batch LLM steam_signals  3) re-embed
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import openai
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.models.game import Game
from app.seed.embeddings import generate_embeddings
from app.seed.games import upsert_game
from app.services.igdb_edition_resolver import resolve_parent_links
from app.sources import summarizer
from app.sources.igdb import fetch_recent_games, fetch_top_games, fetch_upcoming_games
from sqlalchemy import select, update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_CACHE_REVIEWS = Path(".cache/steam_reviews")
_CACHE_BATCHES = Path(".cache/batches")
_CACHE_STATE = Path(".cache/state")

# Q2 since_ts = 2022-01-01 00:00:00 UTC
_SINCE_RECENT_TS = 1640995200
# Q3 until_ts = now + 2 years (approx)
_UNTIL_UPCOMING_SECS = 2 * 365 * 24 * 3600


def _load_state(phase: str) -> dict:
    path = _CACHE_STATE / f"phase_{phase}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"offset": 0, "batch_id": None, "applied_ids": []}


def _save_state(phase: str, state: dict) -> None:
    _CACHE_STATE.mkdir(parents=True, exist_ok=True)
    (_CACHE_STATE / f"phase_{phase}.json").write_text(json.dumps(state))


async def _sync_phase(
    phase: str,
    max_per_query: int,
    force: bool,
    state: dict,
) -> None:
    until_ts = int(datetime.now(timezone.utc).timestamp()) + _UNTIL_UPCOMING_SECS

    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:
            offset = state["offset"]
            total = 0

            for batch_start in range(offset, max_per_query, 500):
                logger.info("[%s] Fetching IGDB offset %d ...", phase, batch_start)

                if phase == "upcoming":
                    igdb_games = await fetch_upcoming_games(client, until_ts, offset=batch_start)
                elif phase == "recent":
                    igdb_games = await fetch_recent_games(client, _SINCE_RECENT_TS, offset=batch_start)
                else:
                    igdb_games = await fetch_top_games(client, offset=batch_start)

                if not igdb_games:
                    logger.info("[%s] No more games at offset %d, done.", phase, batch_start)
                    break

                parent_links: dict[int, int] = {}
                for igdb_game in tqdm(igdb_games, desc=f"{phase} offset={batch_start}"):
                    try:
                        await upsert_game(session, client, igdb_game, force=force)
                        total += 1
                        parent_igdb_id = igdb_game.get("parent_game") or igdb_game.get("version_parent")
                        if parent_igdb_id:
                            parent_links[igdb_game["id"]] = parent_igdb_id
                    except Exception as exc:
                        logger.error("[%s] upsert failed: %s", igdb_game.get("name", "?"), exc)
                        await session.rollback()

                # Pass 2 : résolution des parent_game_id
                if parent_links:
                    await resolve_parent_links(session, parent_links)
                    await session.commit()

                state["offset"] = batch_start + len(igdb_games)
                _save_state(phase, state)

            logger.info("[%s] Sync done — %d games processed", phase, total)


def _build_batch_request(payload: dict) -> dict:
    return {
        "custom_id": payload["game_id"],
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "max_tokens": 800,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "steam_signals", "schema": summarizer._SCHEMA, "strict": True},
            },
            "messages": [
                {"role": "system", "content": summarizer._SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Jeu : {payload['title']}. "
                        f"Genres : {', '.join(payload.get('genres', []))}. "
                        f"Score Steam : {payload.get('steam_score')}% positifs sur "
                        f"{payload.get('steam_total_reviews')} avis.\n\n"
                        f"Avis Steam :\n" +
                        "\n".join(
                            f"- {r.strip()[:400]}"
                            for r in payload.get("reviews", [])[:30]
                            if r.strip()
                        )
                    ),
                },
            ],
        },
    }


async def _submit_chunk(
    client: openai.AsyncOpenAI,
    phase: str,
    chunk_idx: int,
    payloads: list[dict],
    state: dict,
    max_retries: int = 3,
) -> None:
    chunk_path = _CACHE_BATCHES / f"{phase}_chunk{chunk_idx}.jsonl"
    pending = list(payloads)

    for attempt in range(1, max_retries + 1):
        chunk_path.write_text("\n".join(json.dumps(_build_batch_request(p)) for p in pending))

        logger.info("[%s] Chunk %d — uploading %d requests (attempt %d/%d)...",
                    phase, chunk_idx, len(pending), attempt, max_retries)

        with chunk_path.open("rb") as f:
            file_obj = await client.files.create(file=f, purpose="batch")

        batch = await client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )
        state["batch_id"] = batch.id
        _save_state(phase, state)
        logger.info("[%s] Chunk %d — batch submitted: %s", phase, chunk_idx, batch.id)

        while True:
            await asyncio.sleep(60)
            batch = await client.batches.retrieve(batch.id)
            logger.info("[%s] Chunk %d — status: %s", phase, chunk_idx, batch.status)
            if batch.status in ("completed", "failed", "cancelled", "expired"):
                break

        if batch.status != "completed" or not batch.output_file_id:
            logger.error("[%s] Chunk %d — batch %s failed (status=%s), aborting chunk.",
                         phase, chunk_idx, batch.id, batch.status)
            return

        output = await client.files.content(batch.output_file_id)
        failed_ids: list[str] = []

        async with AsyncSessionLocal() as session:
            for line in output.text.splitlines():
                result = json.loads(line)
                game_id = result["custom_id"]
                if result.get("error") or not result.get("response"):
                    failed_ids.append(game_id)
                    continue
                try:
                    content = result["response"]["body"]["choices"][0]["message"]["content"]
                    signals = json.loads(content)
                except (KeyError, json.JSONDecodeError):
                    failed_ids.append(game_id)
                    continue

                game = (await session.execute(
                    select(Game).where(Game.id == game_id)
                )).scalar_one_or_none()
                if game:
                    game.steam_signals = signals
                    state["applied_ids"].append(game_id)

            await session.commit()

        logger.info("[%s] Chunk %d — applied %d, failed %d",
                    phase, chunk_idx, len(state["applied_ids"]), len(failed_ids))
        _save_state(phase, state)

        if not failed_ids or attempt == max_retries:
            break

        pending = [p for p in payloads if p["game_id"] in failed_ids]
        logger.info("[%s] Chunk %d — retrying %d failures...", phase, chunk_idx, len(pending))


async def _batch_llm_phase(phase: str, state: dict, chunk_size: int = 400) -> None:
    _CACHE_BATCHES.mkdir(parents=True, exist_ok=True)

    review_files = list(_CACHE_REVIEWS.glob("*.jsonl"))
    if not review_files:
        logger.info("[%s] No review cache files, skipping LLM batch.", phase)
        return

    already_applied = set(state["applied_ids"])
    payloads = []
    for rf in review_files:
        payload = json.loads(rf.read_text())
        if payload["game_id"] not in already_applied:
            payloads.append(payload)

    if not payloads:
        logger.info("[%s] All review files already applied, skipping LLM batch.", phase)
        return

    logger.info("[%s] %d review files to process (%d already applied), splitting into chunks of %d...",
                phase, len(payloads), len(already_applied), chunk_size)

    client = openai.AsyncOpenAI()
    chunks = [payloads[i:i + chunk_size] for i in range(0, len(payloads), chunk_size)]

    for idx, chunk in enumerate(chunks):
        logger.info("[%s] === Chunk %d/%d ===", phase, idx + 1, len(chunks))
        await _submit_chunk(client, phase, idx + 1, chunk, state)

    logger.info("[%s] All chunks done — total applied: %d", phase, len(state["applied_ids"]))
    _save_state(phase, state)


async def _reembed_all() -> None:
    logger.info("=== reembed — Reset ingestion_hash pour tous les jeux ===")
    async with AsyncSessionLocal() as session:
        await session.execute(update(Game).values(ingestion_hash=None))
        await session.commit()

    logger.info("=== reembed — Génération des embeddings ===")
    async with AsyncSessionLocal() as session:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        count = await generate_embeddings(session, model)
        logger.info("reembed — %d embeddings générés", count)

    logger.info("=== reembed — Phase done ===")


async def main(phase: str, max_per_query: int, force: bool) -> None:
    if phase == "reembed":
        await _reembed_all()
        return

    state = _load_state(phase)

    if state["offset"] > 0:
        answer = input(f"[{phase}] State found at offset {state['offset']}. Resume? [Y/n] ").strip().lower()
        if answer == "n":
            state = {"offset": 0, "batch_id": None, "applied_ids": []}

    # Step 1: Sync
    logger.info("=== [%s] Step 1/3 — IGDB + Steam + SteamSpy sync ===", phase)
    await _sync_phase(phase, max_per_query, force, state)

    # Step 2: LLM batch (skip for upcoming — no reviews)
    if phase != "upcoming":
        logger.info("=== [%s] Step 2/3 — LLM batch steam_signals ===", phase)
        await _batch_llm_phase(phase, state)
    else:
        logger.info("=== [%s] Step 2/3 — skipped (no reviews for upcoming) ===", phase)

    # Step 3: Re-embed
    logger.info("=== [%s] Step 3/3 — Re-embed ===", phase)
    async with AsyncSessionLocal() as session:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        count = await generate_embeddings(session, model)
        logger.info("[%s] Embeddings regenerated: %d", phase, count)

    logger.info("=== [%s] Phase done ===", phase)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GolAi ingest — RAG Data Enrichment")
    parser.add_argument(
        "--phase",
        required=True,
        choices=["upcoming", "recent", "top", "reembed"],
        help="Phase d'ingestion : upcoming (Q3), recent (Q2), top (Q1 + --force requis), reembed (re-embed tous les jeux sans re-fetch API)",
    )
    parser.add_argument(
        "--max-per-query",
        type=int,
        default=99999,
        metavar="N",
        help="Nombre maximum de jeux à fetcher (défaut : illimité)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch les sources pour les jeux déjà en base (requis pour --phase top)",
    )
    args = parser.parse_args()

    asyncio.run(main(
        phase=args.phase,
        max_per_query=args.max_per_query,
        force=args.force,
    ))
