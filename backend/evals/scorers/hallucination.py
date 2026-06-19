"""Hallucination scorer: verifies cited game titles exist in the DB."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.guardrails import extract_candidate_titles, match_titles_in_db
from evals.schema import EvalItem


async def score_hallucination(item: EvalItem, output: str, db: AsyncSession) -> float | None:
    # Toujours checker si un taux max est explicitement attendu (ex : grounding multi-tour sans library)
    if not item.metadata.library and item.expected.max_hallucination_rate is None:
        return None

    candidates = extract_candidate_titles(output)
    if not candidates:
        return None

    matches = await match_titles_in_db(candidates, db)
    unmatched = [t for t, m in matches.items() if m is None]
    return round(len(unmatched) / len(candidates), 3)
