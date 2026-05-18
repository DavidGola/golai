import logging
import sys

import sentry_sdk

from app.sources import psn

logger = logging.getLogger(__name__)


def run(npsso: str) -> int:
    try:
        psn.check_npsso(npsso)
        logger.info("PSN NPSSO OK")
        return 0
    except ValueError as e:
        code = str(e)
        if code == "psn_npsso_invalid":
            sentry_sdk.capture_message("PSN NPSSO expired or invalid", level="error")
            logger.error("PSN NPSSO expired or invalid — Sentry alert sent")
            return 1
        logger.warning("PSN API unavailable — health check skipped")
        return 2


if __name__ == "__main__":
    from app.config import settings
    from app.observability import initialize_sentry

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    initialize_sentry()
    sys.exit(run(settings.psn_npsso.get_secret_value()))
