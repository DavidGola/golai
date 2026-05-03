import uuid

import pytest
import pytest_asyncio
import httpx
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import app.models  # noqa: F401 — registers all models in Base.metadata
from app.database import Base, get_db
from app.models.conversation import Conversation
from app.models.game import Game
from app.models.taxonomy import Genre, Criterion
from app.models.user import User

TEST_DB_URL = "postgresql+asyncpg://golai:golai@localhost:5433/golai_test"
_password_helper = PasswordHelper()


# ─── Session-scoped infra ────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


# ─── Unit test: nested-transaction session (rollback = no TRUNCATE needed) ───


@pytest_asyncio.fixture
async def db_session(test_engine):
    """
    Session with automatic savepoint restart.
    Service commits release the savepoint; the outer transaction is
    rolled back at teardown — no TRUNCATE needed and no lock conflicts.
    """
    async with test_engine.connect() as connection:
        await connection.begin()
        await connection.begin_nested()

        session = AsyncSession(bind=connection, expire_on_commit=False)

        @sa_event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(session_obj, transaction):
            if transaction.nested and not transaction._parent.nested:
                session_obj.begin_nested()

        yield session

        await session.close()
        await connection.rollback()


# ─── Integration test: HTTP client ───────────────────────────────────────────


@pytest_asyncio.fixture
async def app_with_test_db(session_factory):
    from app.main import app

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client(app_with_test_db):
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app_with_test_db),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def user_factory(client):
    async def create(
        email: str = "test@test.fr",
        password: str = "Password123!",
        username: str = "testuser",
    ):
        r = await client.post(
            "/auth/register",
            json={"email": email, "password": password, "username": username},
        )
        assert r.status_code == 201, r.text
        r2 = await client.post(
            "/auth/jwt/login",
            data={"username": email, "password": password},
        )
        assert r2.status_code == 200, r2.text
        return r.json()["id"], r2.json()["access_token"]

    return create


# ─── Unit test data fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def user_a(db_session):
    user = User(
        id=uuid.uuid4(),
        email="usera@test.fr",
        username="usera",
        hashed_password=_password_helper.hash("password"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db_session):
    user = User(
        id=uuid.uuid4(),
        email="userb@test.fr",
        username="userb",
        hashed_password=_password_helper.hash("password"),
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def seeded_game(db_session):
    game = Game(title="Test Game")
    db_session.add(game)
    await db_session.commit()
    await db_session.refresh(game)
    return game


@pytest_asyncio.fixture
async def seeded_genres(db_session):
    genres = [
        Genre(slug="rpg", name="RPG"),
        Genre(slug="action", name="Action"),
    ]
    db_session.add_all(genres)
    await db_session.commit()
    for g in genres:
        await db_session.refresh(g)
    return genres


@pytest_asyncio.fixture
async def seeded_criteria(db_session):
    criteria = [
        Criterion(slug="story", name="Histoire"),
        Criterion(slug="coop", name="Coopération"),
    ]
    db_session.add_all(criteria)
    await db_session.commit()
    for c in criteria:
        await db_session.refresh(c)
    return criteria


@pytest_asyncio.fixture
async def conversation_a(db_session, user_a):
    conv = Conversation(user_id=user_a.id, title="Test conv")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return conv


# ─── IA mocks ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_stream_agent(monkeypatch):
    async def fake_stream(deps, user_message, history):
        yield {"event": "token", "data": "hello "}
        yield {"event": "token", "data": "world"}
        yield {
            "event": "result",
            "data": {
                "output": "hello world",
                "usage": {
                    "total_tokens": 42,
                    "input_tokens": 20,
                    "output_tokens": 22,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                },
            },
        }

    monkeypatch.setattr("app.services.chat.stream_agent", fake_stream)


@pytest.fixture
def mock_stream_agent_error(monkeypatch):
    async def fake_stream_error(deps, user_message, history):
        yield {"event": "error", "data": "LLM unavailable"}

    monkeypatch.setattr("app.services.chat.stream_agent", fake_stream_error)
