"""PSN source — thin wrapper around psnawp isolating Sony API volatility."""
from dataclasses import dataclass
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPForbiddenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
    PSNAWPUnauthorizedError,
)
from requests.exceptions import ConnectionError, Timeout


@dataclass
class PSNGameDTO:
    psn_id: str
    title: str
    cover_url: str | None
    trophy_progress_pct: int | None
    hours_played: float | None


def check_npsso(npsso: str) -> None:
    """Validate NPSSO by instantiating the client (auth is verified at init).

    Raises ValueError with codes: "psn_npsso_invalid", "psn_api_unavailable"
    """
    try:
        PSNAWP(npsso_cookie=npsso)
    except (PSNAWPAuthenticationError, PSNAWPUnauthorizedError):
        raise ValueError("psn_npsso_invalid")
    except (PSNAWPServerError, ConnectionError, Timeout) as exc:
        raise ValueError("psn_api_unavailable") from exc


def fetch_library(npsso: str, online_id: str) -> list[PSNGameDTO]:
    """Fetch user's PSN library combining trophy titles and play time.

    Raises ValueError with codes:
    - "psn_profile_private"
    - "psn_npsso_invalid"
    - "psn_invalid_online_id"
    - "psn_api_unavailable"
    """
    try:
        client = PSNAWP(npsso_cookie=npsso)
        user = client.user(online_id=online_id)
        trophy_list = list(user.trophy_titles())
        stats_list = list(user.title_stats())
    except (PSNAWPAuthenticationError, PSNAWPUnauthorizedError):
        raise ValueError("psn_npsso_invalid")
    except PSNAWPForbiddenError:
        raise ValueError("psn_profile_private")
    except PSNAWPNotFoundError:
        raise ValueError("psn_invalid_online_id")
    except (PSNAWPServerError, ConnectionError, Timeout) as exc:
        raise ValueError("psn_api_unavailable") from exc

    stats_by_title: dict[str, Any] = {
        s.name.lower().strip(): s
        for s in stats_list
        if s.name
    }

    result: list[PSNGameDTO] = []
    for t in trophy_list:
        if t.np_communication_id is None:
            continue
        title_name = t.title_name or f"Game {t.np_communication_id}"
        stats = stats_by_title.get(title_name.lower().strip())
        hours = None
        if stats is not None and stats.play_duration:
            hours = round(stats.play_duration.total_seconds() / 3600, 1)
        result.append(PSNGameDTO(
            psn_id=t.np_communication_id,
            title=title_name,
            cover_url=t.title_icon_url,
            trophy_progress_pct=t.progress,
            hours_played=hours,
        ))
    return result
