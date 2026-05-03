import logging
from howlongtobeatpy import HowLongToBeat

logger = logging.getLogger(__name__)


async def search_game(title: str) -> dict | None:
    try:
        results = await HowLongToBeat().async_search(title)
    except Exception as exc:
        logger.warning("HLTB search failed for %r: %s", title, exc)
        return None

    if not results:
        return None

    best = max(results, key=lambda r: r.similarity)
    if best.similarity < 0.6:
        return None

    def _hours(val) -> float | None:
        return float(val) if val and val > 0 else None

    return {
        "hltb_id": best.game_id,
        "hltb_main": _hours(best.main_story),
        "hltb_extra": _hours(best.main_extra),
        "hltb_completionist": _hours(best.completionist),
    }
