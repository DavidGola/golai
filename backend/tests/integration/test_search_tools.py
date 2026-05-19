"""
Tests d'intégration pour les tools search_catalog et search_owned_games.
Appels directs aux fonctions tools via RunContext (pas via HTTP).
retrieve_games est monkeypatché pour retourner un set connu de jeux
et filtrer selon exclude_ids — on teste le comportement de filtrage.
"""
import uuid

import pytest
import pytest_asyncio
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from app.ai.agent import AgentDeps, AnonymousAgentDeps, anonymous_agent, search_catalog, search_catalog_multi, search_owned_games
from app.models.game import Game
from app.models.user_game import UserGame, UserGameStatus
from app.models.user import User
from fastapi_users.password import PasswordHelper


_password_helper = PasswordHelper()


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def three_games(session_factory):
    """Crée 3 jeux en DB, retourne leur liste."""
    async with session_factory() as db:
        games = [Game(title=f"SearchToolGame{i}") for i in range(3)]
        db.add_all(games)
        await db.commit()
        for g in games:
            await db.refresh(g)
        return list(games)


@pytest_asyncio.fixture
async def auth_user_with_completed(session_factory, three_games):
    """User auth avec le premier jeu marqué completed en Library."""
    async with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            email="searchtool@test.fr",
            username="searchtool",
            hashed_password=_password_helper.hash("password"),
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()
        entry = UserGame(user_id=user.id, game_id=three_games[0].id, status=UserGameStatus.completed)
        db.add(entry)
        await db.commit()
        await db.refresh(user)
        return user


def _make_game_dict(game: Game) -> dict:
    return {"id": str(game.id), "title": game.title}


def _make_fake_retrieve(three_games: list[Game]):
    """Retourne une version mockée de retrieve_games qui filtre par exclude_ids."""
    all_games = [_make_game_dict(g) for g in three_games]

    async def fake_retrieve(db, query, top_k=None, *, exclude_ids=None):
        if exclude_ids:
            return [g for g in all_games if uuid.UUID(g["id"]) not in exclude_ids]
        return list(all_games)

    return fake_retrieve


# ─── Tests ────────────────────────────────────────────────────────────────────


async def test_search_catalog_auth_excludes_completed_game(
    session_factory, three_games, auth_user_with_completed, monkeypatch
):
    """search_catalog en auth exclut le jeu completed de la Library."""
    monkeypatch.setattr("app.ai.agent.retrieve_games", _make_fake_retrieve(three_games))

    async with session_factory() as db:
        user = auth_user_with_completed
        ctx = RunContext(deps=AgentDeps(db=db, user=user), model=TestModel(), usage=RunUsage())
        results = await search_catalog(ctx, "game", 10)

    completed_id = str(three_games[0].id)
    result_ids = [r["id"] for r in results]
    assert completed_id not in result_ids
    assert len(results) == 2


async def test_search_owned_games_auth_includes_completed_game(
    session_factory, three_games, auth_user_with_completed, monkeypatch
):
    """search_owned_games en auth retourne tous les jeux y compris le completed."""
    monkeypatch.setattr("app.ai.agent.retrieve_games", _make_fake_retrieve(three_games))

    async with session_factory() as db:
        user = auth_user_with_completed
        ctx = RunContext(deps=AgentDeps(db=db, user=user), model=TestModel(), usage=RunUsage())
        results = await search_owned_games(ctx, "game", 10)

    assert len(results) == 3
    result_ids = {r["id"] for r in results}
    assert str(three_games[0].id) in result_ids


async def test_search_catalog_anonymous_returns_all(
    session_factory, three_games, monkeypatch
):
    """search_catalog en anonyme retourne tous les jeux (pas de filtre Library)."""
    monkeypatch.setattr("app.ai.agent.retrieve_games", _make_fake_retrieve(three_games))

    async with session_factory() as db:
        ctx = RunContext(deps=AnonymousAgentDeps(db=db), model=TestModel(), usage=RunUsage())
        results = await search_catalog(ctx, "game", 10)

    assert len(results) == 3


def test_search_owned_games_not_in_anonymous_toolset():
    """search_owned_games n'est pas exposé à l'agent anonyme."""
    anon_tool_names = set(anonymous_agent._function_toolset.tools.keys()) | {
        t for ts in anonymous_agent._user_toolsets for t in ts.tools.keys()
    }
    assert "search_owned_games" not in anon_tool_names
