import hashlib
import logging

from sqlalchemy import not_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import Game, GameEmbedding

logger = logging.getLogger(__name__)
MODEL_VERSION = "BAAI/bge-m3"


def build_vector_string(game: Game) -> str:
    genres = ", ".join(g.name for g in game.genres) if game.genres else ""
    platforms = ", ".join(p.name for p in game.platforms) if game.platforms else ""
    modes = ", ".join(m.name for m in game.modes) if game.modes else ""
    tags = ", ".join(t.name for t in game.tags) if game.tags else ""

    keywords = ", ".join(game.keywords) if game.keywords else ""

    parts = [f"{game.title} — {genres} — {game.developer or ''} — {platforms} — {modes}"]
    if tags:
        parts.append(tags)
    if keywords:
        parts.append(keywords)
    if game.steam_description:
        parts.append(game.steam_description[:500])
    elif game.storyline:
        parts.append(game.storyline[:500])
    elif game.summary:
        parts.append(game.summary)
    if game.steam_tags:
        parts.append(f"Steam tags : {', '.join(t.name for t in game.steam_tags[:8])}")
    if game.steam_signals:
        s = game.steam_signals
        parts.append(f"[Avis] {s.get('summary', '')}")
        parts.append(f"Forces : {', '.join(s.get('strengths', []))}")
        parts.append(f"Critiques : {', '.join(s.get('complaints', []))}")
        parts.append(f"Pour : {s.get('target_audience', '')}")
        parts.append(f"Vibes : {', '.join(s.get('vibes', []))}")
        parts.append(f"Émotions : {', '.join(s.get('emotional_tone', []))}")
        parts.append(
            f"Session {s.get('session_shape')} | Pacing {s.get('pacing')} | "
            f"Difficulté {s.get('difficulty')} | Rejouabilité {s.get('replay_value')} | "
            f"Style {s.get('art_style')}"
        )

    hltb_parts = []
    if game.hltb_main:
        hltb_parts.append(f"{game.hltb_main:.0f}h histoire")
    if game.hltb_extra:
        hltb_parts.append(f"{game.hltb_extra:.0f}h extra")
    if game.hltb_completionist:
        hltb_parts.append(f"{game.hltb_completionist:.0f}h complet")
    if hltb_parts:
        parts.append(" / ".join(hltb_parts))

    scores = []
    if game.igdb_rating:
        scores.append(f"IGDB {game.igdb_rating:.0f}/100")
    if game.metacritic_score:
        scores.append(f"Metacritic {game.metacritic_score}/100")
    if game.steam_score:
        if game.steam_total_reviews:
            scores.append(f"Steam {game.steam_score}% ({game.steam_total_reviews} avis)")
        else:
            scores.append(f"Steam {game.steam_score}%")
    if scores:
        parts.append("Score " + " | ".join(scores))

    return " — ".join(filter(None, parts))


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:64]


async def generate_embeddings(session: AsyncSession, model, batch_size: int = 32) -> int:
    active_emb = exists().where(
        (GameEmbedding.game_id == Game.id) & (GameEmbedding.is_active == True)  # noqa: E712
    )
    stmt = (
        select(Game)
        .where(not_(active_emb))
        .options(
            selectinload(Game.genres),
            selectinload(Game.platforms),
            selectinload(Game.modes),
            selectinload(Game.tags),
            selectinload(Game.steam_tags),
            selectinload(Game.embeddings),
        )
    )
    games = (await session.execute(stmt)).scalars().all()

    if not games:
        logger.info("No games need embedding.")
        return 0

    logger.info("Generating embeddings for %d games...", len(games))
    total = 0

    for i in range(0, len(games), batch_size):
        batch = games[i : i + batch_size]
        texts = [build_vector_string(g) for g in batch]
        hashes = [_hash(t) for t in texts]

        logger.info("  Encoding batch %d/%d...", i // batch_size + 1, -(-len(games) // batch_size))
        vectors = model.encode(texts, normalize_embeddings=True)

        for game, text_hash, vector in zip(batch, hashes, vectors):
            # Check if hash changed (skip if same)
            if game.ingestion_hash == text_hash:
                continue
            for emb in game.embeddings:
                emb.is_active = False
            session.add(
                GameEmbedding(
                    game_id=game.id,
                    model_version=MODEL_VERSION,
                    embedding=vector.tolist(),
                    is_active=True,
                )
            )
            game.ingestion_hash = text_hash

        await session.commit()
        total += len(batch)
        logger.info("  Batch done (%d/%d games)", total, len(games))

    return total
