from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rate_limit import RateLimitBucket
from app.models.taxonomy import user_favorite_genres, user_important_criteria
from app.models.user import User


async def get_user_with_relations(db: AsyncSession, user_id) -> User | None:
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.favorite_genres),
            selectinload(User.important_criteria),
        )
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def set_favorite_genres(db: AsyncSession, user_id, genre_ids: list[int]) -> None:
    await db.execute(
        delete(user_favorite_genres).where(user_favorite_genres.c.user_id == user_id)
    )
    if genre_ids:
        await db.execute(
            insert(user_favorite_genres),
            [{"user_id": user_id, "genre_id": gid} for gid in genre_ids],
        )


async def set_important_criteria(db: AsyncSession, user_id, criterion_ids: list[int]) -> None:
    await db.execute(
        delete(user_important_criteria).where(user_important_criteria.c.user_id == user_id)
    )
    if criterion_ids:
        await db.execute(
            insert(user_important_criteria),
            [{"user_id": user_id, "criterion_id": cid} for cid in criterion_ids],
        )


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.bucket_key == f"chat:auth:{user.id}"
        )
    )
    await db.delete(user)
    await db.commit()
