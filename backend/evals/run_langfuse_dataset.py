from __future__ import annotations

import argparse
import asyncio
import json
import sys
import random
import uuid
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401 - registers all SQLAlchemy models
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.game import Game
from app.models.taxonomy import Criterion, Genre
from app.models.user import PlaytimePreference, User
from app.models.user_game import UserGame, UserGameStatus
from app.observability import initialize_langfuse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

DEFAULT_DATASET_PATH = BACKEND_DIR / "evals" / "datasets" / "golai_library_v1.json"
VALID_COMMANDS = {"dry-run", "sync", "run"}
VALID_PLAYTIME = {item.value for item in PlaytimePreference}
VALID_STATUS = {item.value for item in UserGameStatus}
RATE_LIMIT_MARKERS = ("429", "rate limit", "rate_limit", "too many requests")


class DatasetValidationError(ValueError):
    pass


def _slug(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "-" for ch in value.strip()]
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown"


def load_dataset(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    validate_dataset(data)
    return data


def validate_dataset(data: dict[str, Any]) -> None:
    errors: list[str] = []
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        errors.append("dataset.name is required")
    if not isinstance(data.get("items"), list) or not data["items"]:
        errors.append("dataset.items must be a non-empty list")

    seen_ids: set[str] = set()
    for index, item in enumerate(data.get("items", [])):
        prefix = f"items[{index}]"
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{prefix}.id is required")
        elif item_id in seen_ids:
            errors.append(f"{prefix}.id duplicates {item_id!r}")
        else:
            seen_ids.add(item_id)

        if not isinstance(item.get("input"), str) or not item["input"].strip():
            errors.append(f"{prefix}.input is required")
        if not isinstance(item.get("expected_output"), dict):
            errors.append(f"{prefix}.expected_output must be an object")

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"{prefix}.metadata must be an object")
            continue

        profile = metadata.get("profile", {})
        if not isinstance(profile, dict):
            errors.append(f"{prefix}.metadata.profile must be an object")
            profile = {}
        playtime = profile.get("preferred_playtime")
        if playtime is not None and playtime not in VALID_PLAYTIME:
            errors.append(f"{prefix}.metadata.profile.preferred_playtime is invalid: {playtime!r}")

        for field in ("favorite_genres", "important_criteria", "tags"):
            value = profile.get(field) if field != "tags" else metadata.get(field)
            if value is not None and not isinstance(value, list):
                errors.append(f"{prefix}.{field} must be a list")

        library = metadata.get("library")
        if not isinstance(library, list):
            errors.append(f"{prefix}.metadata.library must be a list")
            continue

        for game_index, game in enumerate(library):
            game_prefix = f"{prefix}.metadata.library[{game_index}]"
            if not isinstance(game, dict):
                errors.append(f"{game_prefix} must be an object")
                continue
            if not isinstance(game.get("title"), str) or not game["title"].strip():
                errors.append(f"{game_prefix}.title is required")
            status = game.get("status")
            if status is not None and status not in VALID_STATUS:
                errors.append(f"{game_prefix}.status is invalid: {status!r}")
            rating = game.get("user_rating")
            if rating is not None and (not isinstance(rating, int) or rating < 1 or rating > 10):
                errors.append(f"{game_prefix}.user_rating must be an integer between 1 and 10")
            genres = game.get("genres", [])
            if not isinstance(genres, list):
                errors.append(f"{game_prefix}.genres must be a list")

    if errors:
        raise DatasetValidationError("\n".join(errors))


def _langfuse_client():
    client = initialize_langfuse()
    if client is None:
        raise RuntimeError(
            "Langfuse is not configured. Set LANGFUSE_ENABLED=true, "
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
        )
    return client


def _already_exists(exc: Exception) -> bool:
    text = str(exc).lower()
    return "already exists" in text or "conflict" in text or "409" in text


def sync_dataset(dataset: dict[str, Any]) -> None:
    client = _langfuse_client()
    try:
        client.create_dataset(
            name=dataset["name"],
            description=dataset.get("description"),
            metadata=dataset.get("metadata"),
        )
        print(f"Created dataset {dataset['name']}")
    except Exception as exc:
        if not _already_exists(exc):
            raise
        print(f"Dataset {dataset['name']} already exists")

    for item in dataset["items"]:
        client.create_dataset_item(
            dataset_name=dataset["name"],
            id=f"{dataset['name']}-{item['id']}",
            input=item["input"],
            expected_output=item["expected_output"],
            metadata=item["metadata"],
        )
    print(f"Synced {len(dataset['items'])} dataset items")


async def _get_or_create_genre(db: AsyncSession, name: str) -> Genre:
    slug = _slug(name)
    result = await db.execute(select(Genre).where(Genre.slug == slug))
    genre = result.scalar_one_or_none()
    if genre is not None:
        return genre
    genre = Genre(slug=slug, name=name)
    db.add(genre)
    await db.flush()
    return genre


async def _get_or_create_criterion(db: AsyncSession, name: str) -> Criterion:
    slug = _slug(name)
    result = await db.execute(select(Criterion).where(Criterion.slug == slug))
    criterion = result.scalar_one_or_none()
    if criterion is not None:
        return criterion
    criterion = Criterion(slug=slug, name=name)
    db.add(criterion)
    await db.flush()
    return criterion


async def create_eval_fixture(db: AsyncSession, item: dict[str, Any]) -> User:
    metadata = item.get("metadata", {})
    profile = metadata.get("profile", {})
    suffix = uuid.uuid4().hex[:8]
    playtime = profile.get("preferred_playtime")
    favorite_genres = [
        await _get_or_create_genre(db, name)
        for name in profile.get("favorite_genres", [])
    ]
    important_criteria = [
        await _get_or_create_criterion(db, name)
        for name in profile.get("important_criteria", [])
    ]

    user = User(
        id=uuid.uuid4(),
        email=f"eval+{item['id']}-{suffix}@golai.local",
        username=f"eval_{_slug(item['id']).replace('-', '_')}_{suffix}",
        hashed_password="eval-only",
        preferred_playtime=PlaytimePreference(playtime) if playtime else None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    user.favorite_genres = favorite_genres
    user.important_criteria = important_criteria
    db.add(user)
    await db.flush()

    for game_data in metadata.get("library", []):
        game = Game(
            title=game_data["title"],
            summary=game_data.get("summary") or f"Fixture d'evaluation pour {game_data['title']}.",
            hltb_main=game_data.get("hltb_main"),
            steam_score=game_data.get("steam_score"),
            steam_total_reviews=game_data.get("steam_total_reviews"),
            metacritic_score=game_data.get("metacritic_score"),
            opencritic_signals=(
                {"score": game_data["opencritic_score"]}
                if game_data.get("opencritic_score") is not None
                else None
            ),
            igdb_rating=game_data.get("igdb_rating"),
        )
        game.genres = [
            await _get_or_create_genre(db, name)
            for name in game_data.get("genres", [])
        ]
        db.add(game)
        await db.flush()

        status = game_data.get("status")
        db.add(
            UserGame(
                user_id=user.id,
                game_id=game.id,
                status=UserGameStatus(status) if status else None,
                user_rating=game_data.get("user_rating"),
                hours_played=game_data.get("hours_played"),
                source="eval",
            )
        )

    await db.flush()
    return user


async def load_eval_user_for_agent(db: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.favorite_genres), selectinload(User.important_criteria))
        .where(User.id == user_id)
    )
    return result.scalar_one()


async def run_dataset_item(item: dict[str, Any]) -> dict[str, Any]:
    from app.ai.agent import AgentDeps, agent as auth_agent
    from app.ai.stream import stream_agent

    async with AsyncSessionLocal() as db:
        transaction = await db.begin()
        try:
            fixture_user = await create_eval_fixture(db, item)
            user = await load_eval_user_for_agent(db, fixture_user.id)
            deps = AgentDeps(db=db, user=user)
            output = ""
            tools: list[str] = []
            usage: dict[str, Any] = {}

            async for event in stream_agent(auth_agent, deps, item["input"], []):
                if event["event"] == "tool":
                    tools.append(event["data"])
                elif event["event"] == "result":
                    output = event["data"]["output"]
                    usage = event["data"].get("usage", {})
                elif event["event"] == "error":
                    raise RuntimeError(event["data"])

            return {
                "answer": output,
                "tools": tools,
                "usage": usage,
                "model": settings.litellm_model,
            }
        finally:
            await transaction.rollback()


async def run_dataset_item_multiturn(
    item: dict[str, Any],
    prior_turns: list[str],
) -> dict[str, Any]:
    """Runner multi-tour pour les evals de grounding.

    Exécute les prior_turns pour construire l'historique de conversation,
    puis run le tour principal (item["input"]) et retourne sa sortie.
    Utilise agent.run() non-streaming (eval uniquement — pas de streaming SSE).
    """
    from app.ai.agent import AgentDeps, agent as auth_agent

    async with AsyncSessionLocal() as db:
        transaction = await db.begin()
        try:
            fixture_user = await create_eval_fixture(db, item)
            user = await load_eval_user_for_agent(db, fixture_user.id)
            deps = AgentDeps(db=db, user=user)

            history: list = []
            for turn_msg in prior_turns:
                result = await auth_agent.run(turn_msg, message_history=history, deps=deps)
                history = list(result.all_messages())

            final = await auth_agent.run(item["input"], message_history=history, deps=deps)
            usage_obj = final.usage()
            return {
                "answer": final.output,
                "tools": [],
                "usage": {
                    "input_tokens": usage_obj.input_tokens or 0,
                    "output_tokens": usage_obj.output_tokens or 0,
                },
                "model": settings.litellm_model,
            }
        finally:
            await transaction.rollback()


def is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in RATE_LIMIT_MARKERS)


async def run_dataset_item_with_retries(
    item: dict[str, Any],
    *,
    retry_count: int,
    retry_base_delay: float,
) -> dict[str, Any]:
    attempts = max(1, retry_count + 1)
    for attempt in range(1, attempts + 1):
        try:
            result = await run_dataset_item(item)
            if attempt > 1:
                result["retry_attempts"] = attempt - 1
            return result
        except RuntimeError as exc:
            if attempt == attempts or not is_rate_limit_error(exc):
                raise
            delay = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(
                f"Item {item['id']} hit rate limit; retrying in {delay:.1f}s "
                f"({attempt}/{retry_count})"
            )
            await asyncio.sleep(delay)

    raise RuntimeError("unreachable retry state")


def _case_from_langfuse_item(item: Any) -> dict[str, Any]:
    input_value = getattr(item, "input", None)
    expected_output = getattr(item, "expected_output", None)
    metadata = getattr(item, "metadata", None)
    item_id = getattr(item, "id", None) or uuid.uuid4().hex
    return {
        "id": str(item_id),
        "input": input_value,
        "expected_output": expected_output or {},
        "metadata": metadata or {},
    }


def _experiment_item_metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata", None) or {}
    library = metadata.get("library", [])
    return {
        "tags": metadata.get("tags", []),
        "profile": metadata.get("profile", {}),
        "library_size": len(library) if isinstance(library, list) else 0,
    }


def run_experiment(
    dataset_name: str,
    run_name: str | None,
    max_concurrency: int,
    retry_count: int,
    retry_base_delay: float,
) -> None:
    client = _langfuse_client()
    dataset = client.get_dataset(dataset_name)
    experiment_items = [
        {
            "input": item.input,
            "expected_output": item.expected_output,
            "metadata": _experiment_item_metadata(item),
            "_golai_case": _case_from_langfuse_item(item),
        }
        for item in dataset.items
    ]

    async def task(*, item: Any, **_: Any) -> dict[str, Any]:
        case = item["_golai_case"]
        validate_dataset({"name": dataset_name, "items": [case]})
        return await run_dataset_item_with_retries(
            case,
            retry_count=retry_count,
            retry_base_delay=retry_base_delay,
        )

    result = client.run_experiment(
        name=f"{dataset_name}-golai-response-quality",
        run_name=run_name,
        description="GolAi response quality run without automatic judge.",
        data=experiment_items,
        task=task,
        max_concurrency=max_concurrency,
        metadata={"model": settings.litellm_model},
    )
    print(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync or run GolAi Langfuse datasets.")
    parser.add_argument("command", nargs="?", default="dry-run", help="dry-run, sync or run")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--dataset-name", default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--retry-count", type=int, default=3)
    parser.add_argument("--retry-base-delay", type=float, default=10.0)
    parser.add_argument("--dry-run", action="store_true", help="Validate the local dataset and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    command = "dry-run" if args.dry_run else args.command
    if command not in VALID_COMMANDS:
        raise SystemExit(f"Invalid command {command!r}. Expected one of: {', '.join(sorted(VALID_COMMANDS))}")

    dataset = load_dataset(args.dataset)
    if command == "dry-run":
        print(f"Dataset {dataset['name']} is valid ({len(dataset['items'])} items)")
        return
    if command == "sync":
        sync_dataset(dataset)
        return

    dataset_name = args.dataset_name or dataset["name"]
    asyncio.run(
        asyncio.to_thread(
            run_experiment,
            dataset_name,
            args.run_name,
            args.max_concurrency,
            args.retry_count,
            args.retry_base_delay,
        )
    )


if __name__ == "__main__":
    main()
