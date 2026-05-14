"""Deterministic scorers for GolAi eval framework."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.guardrails import extract_candidate_titles
from evals.schema import EvalItem

_MATCH_THRESHOLD = 0.4


def _title_in_output(title: str, output: str) -> bool:
    return title.lower() in output.lower()


def score_must_cite_one_of(item: EvalItem, output: str) -> bool | None:
    if not item.expected.must_cite_one_of:
        return None
    return any(_title_in_output(t, output) for t in item.expected.must_cite_one_of)


def score_must_not_cite(item: EvalItem, output: str) -> bool | None:
    if not item.expected.must_not_cite:
        return None
    return not any(_title_in_output(t, output) for t in item.expected.must_not_cite)


def score_library_anchored(item: EvalItem, output: str) -> float | None:
    if not item.metadata.library:
        return None
    library_titles = {g.title.lower() for g in item.metadata.library}
    cited = extract_candidate_titles(output)
    if not cited:
        return 0.0
    anchored = sum(1 for t in cited if t.lower() in library_titles)
    return round(anchored / len(cited), 3)


async def score_must_cite_property(
    item: EvalItem, output: str, db: AsyncSession
) -> bool | None:
    prop = item.expected.must_cite_property
    if prop is None:
        return None

    cited = extract_candidate_titles(output)
    if not cited:
        return False

    library_map = {g.title.lower(): g for g in item.metadata.library}

    for candidate in cited:
        lib_game = library_map.get(candidate.lower())

        if prop.status_in is not None:
            if lib_game is None or lib_game.status not in prop.status_in:
                continue

        if prop.hltb_main_lte is not None:
            hltb = lib_game.hltb_main if lib_game else None
            if hltb is None:
                hltb = await _db_scalar(
                    db, "SELECT hltb_main FROM games WHERE similarity(title, :q) >= :t ORDER BY similarity(title, :q) DESC LIMIT 1",
                    candidate,
                )
            if hltb is None or hltb > prop.hltb_main_lte:
                continue

        if prop.hltb_main_gte is not None:
            hltb = lib_game.hltb_main if lib_game else None
            if hltb is None:
                hltb = await _db_scalar(
                    db, "SELECT hltb_main FROM games WHERE similarity(title, :q) >= :t ORDER BY similarity(title, :q) DESC LIMIT 1",
                    candidate,
                )
            if hltb is None or hltb < prop.hltb_main_gte:
                continue

        if prop.developer_in is not None:
            dev: str | None = await _db_scalar(
                db, "SELECT developer FROM games WHERE similarity(title, :q) >= :t ORDER BY similarity(title, :q) DESC LIMIT 1",
                candidate,
            )
            if not dev or not any(d.lower() in dev.lower() for d in prop.developer_in):
                continue

        if prop.release_year is not None:
            year: int | None = await _db_scalar(
                db,
                "SELECT EXTRACT(YEAR FROM release_date)::int FROM games WHERE similarity(title, :q) >= :t ORDER BY similarity(title, :q) DESC LIMIT 1",
                candidate,
            )
            if year != prop.release_year:
                continue

        if prop.mode_in is not None:
            modes = await _db_list(
                db,
                """
                SELECT gm.name FROM game_modes gm
                JOIN games_modes gmj ON gmj.mode_id = gm.id
                JOIN games g ON g.id = gmj.game_id
                WHERE similarity(g.title, :q) >= :t
                ORDER BY similarity(g.title, :q) DESC
                LIMIT 20
                """,
                candidate,
            )
            if not any(m in modes for m in prop.mode_in):
                continue

        return True

    return False


async def _db_scalar(db: AsyncSession, query: str, title: str):
    row = await db.execute(text(query), {"q": title, "t": _MATCH_THRESHOLD})
    return row.scalar_one_or_none()


async def _db_list(db: AsyncSession, query: str, title: str) -> list[str]:
    rows = await db.execute(text(query), {"q": title, "t": _MATCH_THRESHOLD})
    return [r[0] for r in rows]


def score_min_word_count(item: EvalItem, output: str) -> bool | None:
    if item.expected.min_word_count is None:
        return None
    word_count = len(output.split())
    return word_count >= item.expected.min_word_count


async def score_item(item: EvalItem, output: str, db: AsyncSession) -> dict:
    must_cite = score_must_cite_one_of(item, output)
    must_not = score_must_not_cite(item, output)
    anchored = score_library_anchored(item, output)
    prop = await score_must_cite_property(item, output, db)
    word_count_ok = score_min_word_count(item, output)

    return {
        "must_cite_one_of": float(must_cite) if must_cite is not None else None,
        "must_not_cite": float(must_not) if must_not is not None else None,
        "library_anchor_rate": anchored,
        "must_cite_property": float(prop) if prop is not None else None,
        "min_word_count_ok": float(word_count_ok) if word_count_ok is not None else None,
    }
