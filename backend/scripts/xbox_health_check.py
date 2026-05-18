import logging
import sys

import sentry_sdk

from app.sources import xbox

logger = logging.getLogger(__name__)


def run(api_key: str) -> int:
    try:
        xbox.check_api_key(api_key)
        logger.info("OpenXBL API key OK")
        return 0
    except ValueError as e:
        code = str(e)
        if code == "xbox_api_key_invalid":
            sentry_sdk.capture_message("OpenXBL API key invalid", level="error")
            logger.error("OpenXBL API key invalid — Sentry alert sent")
            return 1
        if code == "xbox_quota_exceeded":
            sentry_sdk.capture_message("OpenXBL quota near limit", level="warning")
            logger.warning("OpenXBL quota near limit — Sentry alert sent")
            return 0
        logger.warning("OpenXBL API unavailable — health check skipped")
        return 0


if __name__ == "__main__":
    from app.config import settings
    from app.observability import initialize_sentry

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    initialize_sentry()
    sys.exit(run(settings.openxbl_api_key.get_secret_value()))
