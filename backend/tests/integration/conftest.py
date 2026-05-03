import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(session_factory):
    """Truncates transient tables after each integration test."""
    yield
    async with session_factory() as session:
        await session.execute(text(
            "TRUNCATE TABLE users, games, genres, criteria RESTART IDENTITY CASCADE"
        ))
        await session.commit()
