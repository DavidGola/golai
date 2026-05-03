from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit import RateLimitBucket

WINDOW_SECONDS = 60 * 60


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    retry_after: int


def current_hour(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def seconds_until_next_window(window_start: datetime, now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    next_window = as_utc(window_start) + timedelta(seconds=WINDOW_SECONDS)
    retry_after = (next_window - current.astimezone(timezone.utc)).total_seconds()
    return max(1, int(retry_after))


async def check_chat_rate_limit(
    db: AsyncSession,
    bucket_key: str,
    scope: str,
    limit: int,
    now: datetime | None = None,
) -> None:
    if limit <= 0:
        return

    window_start = current_hour(now)
    await db.execute(
        insert(RateLimitBucket)
        .values(
            bucket_key=bucket_key,
            scope=scope,
            window_start=window_start,
            request_count=0,
        )
        .on_conflict_do_nothing(index_elements=[RateLimitBucket.bucket_key])
    )

    result = await db.execute(
        select(RateLimitBucket)
        .where(RateLimitBucket.bucket_key == bucket_key)
        .with_for_update()
    )
    bucket = result.scalar_one()

    bucket_window_start = as_utc(bucket.window_start)

    if bucket_window_start < window_start:
        bucket.scope = scope
        bucket.window_start = window_start
        bucket.request_count = 1
        await db.commit()
        return

    if bucket.request_count >= limit:
        await db.rollback()
        raise RateLimitExceeded(seconds_until_next_window(bucket_window_start, now))

    bucket.scope = scope
    bucket.request_count += 1
    await db.commit()
