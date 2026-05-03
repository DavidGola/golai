import pytest

from app.models.game import Game
from app.models.taxonomy import Criterion, Genre
from app.models.user import User
from app.models.user_game import UserGame
from evals import run_langfuse_dataset
from evals.run_langfuse_dataset import (
    DEFAULT_DATASET_PATH,
    DatasetValidationError,
    create_eval_fixture,
    is_rate_limit_error,
    load_eval_user_for_agent,
    load_dataset,
    validate_dataset,
)


def test_default_dataset_is_valid():
    dataset = load_dataset(DEFAULT_DATASET_PATH)

    assert dataset["name"] == "golai-library-v1"
    assert len(dataset["items"]) >= 10


def test_dataset_validation_rejects_invalid_status():
    dataset = {
        "name": "invalid",
        "items": [
            {
                "id": "bad-status",
                "input": "Question",
                "expected_output": {},
                "metadata": {
                    "profile": {},
                    "library": [
                        {
                            "title": "Bad Fixture",
                            "status": "playing",
                            "genres": [],
                        }
                    ],
                },
            }
        ],
    }

    with pytest.raises(DatasetValidationError, match="status is invalid"):
        validate_dataset(dataset)


def test_is_rate_limit_error_detects_provider_429():
    exc = RuntimeError(
        "status_code: 429, model_name: glm-4.7-flash, "
        "body: {'code': '1305', 'message': 'The service may be temporarily overloaded'}"
    )

    assert is_rate_limit_error(exc) is True


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


async def test_create_eval_fixture_builds_profile_and_library(monkeypatch):
    item = load_dataset(DEFAULT_DATASET_PATH)["items"][0]
    db_session = FakeSession()

    async def fake_get_or_create_genre(_db, name):
        return Genre(slug=name.lower().replace(" ", "-"), name=name)

    async def fake_get_or_create_criterion(_db, name):
        return Criterion(slug=name.lower().replace(" ", "-"), name=name)

    monkeypatch.setattr(run_langfuse_dataset, "_get_or_create_genre", fake_get_or_create_genre)
    monkeypatch.setattr(run_langfuse_dataset, "_get_or_create_criterion", fake_get_or_create_criterion)

    user = await create_eval_fixture(db_session, item)
    games = [obj for obj in db_session.added if isinstance(obj, Game)]
    user_games = [obj for obj in db_session.added if isinstance(obj, UserGame)]

    assert user.email.startswith("eval+weekend-short-owned-")
    assert user.preferred_playtime.value == "short"
    assert {genre.name for genre in user.favorite_genres} == {"Action", "Roguelite"}
    assert len([obj for obj in db_session.added if isinstance(obj, User)]) == 1
    assert len(games) == 3
    assert len(user_games) == 3
    assert {game.title for game in games} == {
        "Hades",
        "A Short Hike",
        "Persona 5 Royal",
    }
    assert {user_game.status.value for user_game in user_games} == {"completed", "not_started", "todo"}


async def test_load_eval_user_for_agent_eager_loads_profile_relations(monkeypatch):
    calls = []

    class FakeResult:
        def scalar_one(self):
            return "loaded-user"

    class FakeAsyncSession:
        async def execute(self, stmt):
            calls.append(str(stmt))
            return FakeResult()

    loaded = await load_eval_user_for_agent(FakeAsyncSession(), "user-id")

    assert loaded == "loaded-user"
    assert calls
    assert "users.id" in calls[0]
