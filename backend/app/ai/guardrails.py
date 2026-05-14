"""Utilities for extracting and matching game titles in agent output."""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_BOLD = re.compile(r"\*\*([^*]{2,80})\*\*")
_QUOTED = re.compile(r'"([^"]{3,80})"')

_MATCH_THRESHOLD = 0.4


def extract_candidate_titles(output: str) -> list[str]:
    """Extract candidate game titles from markdown agent output (bold first, then quoted)."""
    seen: set[str] = set()
    results: list[str] = []
    for pattern in (_BOLD, _QUOTED):
        for m in pattern.finditer(output):
            candidate = m.group(1).strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                results.append(candidate)
    return results


async def match_titles_in_db(
    titles: list[str],
    db: AsyncSession,
    threshold: float = _MATCH_THRESHOLD,
) -> dict[str, str | None]:
    """
    For each candidate title return the best-matching game.title in DB, or None.
    Uses pg_trgm similarity — requires pg_trgm extension.
    """
    if not titles:
        return {}
    results: dict[str, str | None] = {}
    for title in titles:
        row = await db.execute(
            text(
                "SELECT title FROM games "
                "WHERE similarity(title, :q) >= :t "
                "ORDER BY similarity(title, :q) DESC LIMIT 1"
            ),
            {"q": title, "t": threshold},
        )
        results[title] = row.scalar_one_or_none()
    return results
