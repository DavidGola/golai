"""Scorer de notoriété pour les evals re-rank.

Vérifie que les jeux cités par l'agent ont une notoriété moyenne
au-dessus du seuil défini dans EvalExpected.min_notoriety_score.

La notoriété est calculée comme le percentile max(p_steam, p_igdb) du jeu
dans le catalogue — même formule que rerank_by_notoriety (rag.py).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.guardrails import extract_candidate_titles
from evals.schema import EvalItem

_MATCH_THRESHOLD = 0.4

_NOTORIETY_SQL = text("""
WITH ranked AS (
    SELECT
        title,
        CUME_DIST() OVER (ORDER BY COALESCE(steam_total_reviews, 0)) AS p_steam,
        CUME_DIST() OVER (ORDER BY COALESCE(igdb_rating_count, 0))   AS p_igdb
    FROM games
)
SELECT p_steam, p_igdb
FROM ranked
WHERE similarity(title, :q) >= :t
ORDER BY similarity(title, :q) DESC
LIMIT 1
""")


async def score_notoriety(
    item: EvalItem,
    output: str,
    db: AsyncSession | None,
) -> float | None:
    """Retourne la notoriété moyenne des jeux cités, ou None si pas de seuil configuré.

    Seuil de passage : item.expected.min_notoriety_score
    Valeur 0.0–1.0 : percentile max(p_steam, p_igdb) dans le catalogue.
    Seuil calibré : 0.6 (60e percentile, run du 2026-06-19 → score observé 0.826).
    """
    if item.expected.min_notoriety_score is None:
        return None

    candidates = extract_candidate_titles(output)
    if not candidates:
        return 0.0

    if db is None:
        return None

    scores: list[float] = []
    for title in candidates:
        row = await db.execute(_NOTORIETY_SQL, {"q": title, "t": _MATCH_THRESHOLD})
        result = row.one_or_none()
        if result is None:
            scores.append(0.0)
            continue
        p_steam, p_igdb = result
        notoriety = max(
            v for v in (p_steam, p_igdb) if v is not None
        ) if any(v is not None for v in (p_steam, p_igdb)) else 0.5
        scores.append(notoriety)

    return round(sum(scores) / len(scores), 3) if scores else 0.0
