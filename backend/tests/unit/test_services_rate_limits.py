from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.rate_limit import RateLimitBucket
from app.services.rate_limits import RateLimitExceeded, check_chat_rate_limit, current_hour


async def test_check_chat_rate_limit_creates_bucket(db_session):
    now = datetime(2026, 5, 1, 12, 15, tzinfo=timezone.utc)

    await check_chat_rate_limit(db_session, "chat:auth:user-a", "chat:auth", limit=2, now=now)

    bucket = (
        await db_session.execute(
            select(RateLimitBucket).where(RateLimitBucket.bucket_key == "chat:auth:user-a")
        )
    ).scalar_one()
    assert bucket.scope == "chat:auth"
    assert bucket.window_start == current_hour(now)
    assert bucket.request_count == 1


async def test_check_chat_rate_limit_rejects_above_limit(db_session):
    now = datetime(2026, 5, 1, 12, 15, tzinfo=timezone.utc)

    await check_chat_rate_limit(db_session, "chat:auth:user-b", "chat:auth", limit=2, now=now)
    await check_chat_rate_limit(db_session, "chat:auth:user-b", "chat:auth", limit=2, now=now)

    with pytest.raises(RateLimitExceeded) as exc_info:
        await check_chat_rate_limit(db_session, "chat:auth:user-b", "chat:auth", limit=2, now=now)

    assert exc_info.value.retry_after > 0


async def test_check_chat_rate_limit_resets_after_window(db_session):
    now = datetime(2026, 5, 1, 12, 15, tzinfo=timezone.utc)
    next_window = now + timedelta(hours=1)

    await check_chat_rate_limit(db_session, "chat:auth:user-c", "chat:auth", limit=1, now=now)
    await check_chat_rate_limit(db_session, "chat:auth:user-c", "chat:auth", limit=1, now=next_window)

    bucket = (
        await db_session.execute(
            select(RateLimitBucket).where(RateLimitBucket.bucket_key == "chat:auth:user-c")
        )
    ).scalar_one()
    assert bucket.window_start == current_hour(next_window)
    assert bucket.request_count == 1
