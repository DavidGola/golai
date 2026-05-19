"""
library_import_service — orchestration générique des imports de Library externes.

Pattern : un Protocol `LibraryImportSource` décrit ce qui varie d'une source
à l'autre (Steam / PSN / Xbox / Nintendo / Epic / GOG…). Le service contient
l'orchestration partagée :

    resolve_account → fetch_owned → match by source_id → fuzzy fallback
        → create minimal Games → detect dupes → build preview → commit

Pour ajouter un store (memory : multi-store anticipé), il suffit d'implémenter
le Protocol — pas de copier-coller de 130 LOC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.user import User
from app.models.user_game import UserGame, UserGameStatus


# ─── Types intermédiaires (interne au service générique) ─────────────────────


@dataclass
class ExternalOwnedGame:
    """Format normalisé d'un jeu possédé tel que retourné par l'API externe.
    Chaque adapter convertit son DTO source en ce format."""
    source_id: str
    title: str
    cover_url: str | None
    playtime_minutes: int | None = None     # Steam
    completion_pct: int | None = None       # PSN trophy %, Xbox achievement %
    extra_store_url: str | None = None      # Xbox marketplace URL


@dataclass
class InternalPreviewItem:
    """État intermédiaire : Game DB matché + données externes + flags."""
    game: Game
    external: ExternalOwnedGame
    already_in_library: bool
    suggested_status: UserGameStatus | None


# ─── Protocol : ce que chaque source d'import doit fournir ───────────────────


class LibraryImportSource(Protocol):
    """Adapter pour une source d'import (Steam, PSN, Xbox, …).

    Le seam unique pour ajouter un nouveau store : implémenter ce Protocol.
    """

    source_name: str
    """Slug utilisé dans `UserGame.source` (ex: "steam", "psn", "xbox")."""

    use_fuzzy_title_match: bool
    """Si True, tente un match pg_trgm sur le titre quand source_id ne matche
    pas (cas PSN/Xbox où l'API externe ne fournit pas l'id Steam). False pour
    Steam où l'appid est canonique."""

    user_account_attr: str
    """Nom de l'attribut User qui stocke l'identifiant de compte
    (ex: "steam_id", "psn_online_id", "xbox_gamertag")."""

    user_sync_at_attr: str
    """Nom de l'attribut User qui stocke le timestamp de dernier sync."""

    game_source_id_attr: str
    """Nom de la colonne Game.* qui stocke l'identifiant source
    (ex: "steam_id", "psn_id", "xbox_id")."""

    async def resolve_account(self, raw_input: str) -> tuple[Any, Any]:
        """Convertit l'input user en (api_id, storage_value).

        - api_id : identifiant utilisé pour appeler fetch_owned (peut être technique,
          ex: xuid Xbox, steamid64).
        - storage_value : ce qu'on persiste sur user.{user_account_attr} (typiquement
          ce que le user a tapé : vanity URL Steam, gamertag Xbox, online_id PSN).

        Souvent les deux sont identiques (PSN : online_id sert pour les deux).
        Mais Xbox a besoin du xuid pour l'API et garde le gamertag user-friendly.

        Raises ValueError avec un code spécifique source (ex: "steam_invalid_input",
        "psn_npsso_invalid") en cas d'échec.
        """
        ...

    async def fetch_owned(self, account_id: Any) -> list[ExternalOwnedGame]:
        """Récupère la liste brute des jeux possédés, normalisée."""
        ...

    def cast_source_id_for_db(self, source_id: str) -> Any:
        """Convertit le source_id (str générique) au type DB attendu
        (Steam stocke en Integer, PSN/Xbox en String)."""
        ...


# ─── Helpers partagés ────────────────────────────────────────────────────────


def suggest_status_from_completion_pct(pct: int | None) -> UserGameStatus | None:
    """Mapping commun PSN/Xbox : completion percentage → suggested status.
    Steam utilise un mapping différent (playtime-based) — pas applicable ici.
    """
    if pct is None:
        return None
    if pct == 100:
        return UserGameStatus.completed
    if pct > 0:
        return UserGameStatus.todo
    return UserGameStatus.not_started


# ─── Orchestration : build_preview ───────────────────────────────────────────


async def _fuzzy_match_by_title(
    db: AsyncSession, title: str, source_id_attr: str
) -> Game | None:
    """Match pg_trgm sur le titre, en excluant les rows déjà tagged par cette source."""
    result = await db.execute(
        text(
            f"SELECT id FROM games "
            f"WHERE {source_id_attr} IS NULL AND similarity(title, :title) >= 0.6 "
            f"ORDER BY similarity(title, :title) DESC LIMIT 1"
        ),
        {"title": title},
    )
    row = result.fetchone()
    if not row:
        return None
    return await db.get(Game, row[0])


async def build_preview_generic(
    db: AsyncSession,
    user: User,
    raw_input: str,
    source: LibraryImportSource,
) -> tuple[list[InternalPreviewItem], str]:
    """Orchestration partagée Steam/PSN/Xbox/futurs.

    Retourne (items, storage_value). Le caller projette les items vers son
    schema response, et doit passer storage_value à confirm_import_generic
    pour que le compte soit associé à l'utilisateur uniquement lors du confirm.
    """
    api_id, storage_value = await source.resolve_account(raw_input)
    externals = await source.fetch_owned(api_id)

    if not externals:
        return [], storage_value

    # Match par source_id existing
    source_ids = [source.cast_source_id_for_db(e.source_id) for e in externals]
    game_col = getattr(Game, source.game_source_id_attr)
    rows = (await db.execute(select(Game).where(game_col.in_(source_ids)))).scalars().all()
    games_by_source_id: dict[str, Game] = {}
    for g in rows:
        sid = getattr(g, source.game_source_id_attr)
        if sid is not None:
            games_by_source_id[str(sid)] = g

    # Fuzzy match optionnel + création des Games manquants
    for ext in externals:
        if ext.source_id in games_by_source_id:
            continue

        if source.use_fuzzy_title_match:
            matched = await _fuzzy_match_by_title(db, ext.title, source.game_source_id_attr)
            if matched is not None:
                games_by_source_id[ext.source_id] = matched
                continue

        # Création minimal Game
        new_game_kwargs: dict[str, Any] = {
            "title": ext.title,
            "cover_url": ext.cover_url,
            source.game_source_id_attr: source.cast_source_id_for_db(ext.source_id),
        }
        if ext.extra_store_url and source.source_name == "xbox":
            new_game_kwargs["store_urls"] = {"xbox": ext.extra_store_url}
        game = Game(**new_game_kwargs)
        db.add(game)
        games_by_source_id[ext.source_id] = game

    await db.flush()

    # Detect existing library entries
    existing_game_ids = set(
        (await db.execute(
            select(UserGame.game_id).where(UserGame.user_id == user.id)
        )).scalars().all()
    )

    # Build internal items
    items: list[InternalPreviewItem] = []
    for ext in externals:
        game = games_by_source_id.get(ext.source_id)
        if game is None:
            continue

        # Suggested status : completion_pct si fourni (PSN/Xbox), sinon
        # règle Steam (playtime == 0 → not_started).
        if ext.completion_pct is not None:
            suggested = suggest_status_from_completion_pct(ext.completion_pct)
        elif ext.playtime_minutes is not None:
            suggested = UserGameStatus.not_started if ext.playtime_minutes == 0 else None
        else:
            suggested = None

        items.append(InternalPreviewItem(
            game=game,
            external=ext,
            already_in_library=game.id in existing_game_ids,
            suggested_status=suggested,
        ))

    await db.commit()
    return items, storage_value


# ─── Orchestration : confirm_import ──────────────────────────────────────────


async def confirm_import_generic(
    db: AsyncSession,
    user: User,
    items: list[Any],
    source: LibraryImportSource,
    extract_hours_played: Callable[[Any], float | None],
    account_value: str,
) -> tuple[int, int]:
    """Insert UserGame rows, skip dupes. Returns (imported, skipped).

    `items` : list de ConfirmItem (per-source schema), contenant au minimum
    game_id + status + user_rating + review.
    `extract_hours_played` : lambda qui extrait les heures jouées depuis
    l'item (Steam: hours_on_record, PSN: hours_played, Xbox: None).
    `account_value` : valeur à stocker sur user.{source.user_account_attr}.
    """
    if not items:
        return 0, 0

    game_ids = [item.game_id for item in items]
    existing = set(
        (await db.execute(
            select(UserGame.game_id)
            .where(UserGame.user_id == user.id)
            .where(UserGame.game_id.in_(game_ids))
        )).scalars().all()
    )

    imported = 0
    skipped = 0
    for item in items:
        if item.game_id in existing:
            skipped += 1
            continue
        db.add(UserGame(
            user_id=user.id,
            game_id=item.game_id,
            status=item.status,
            user_rating=item.user_rating,
            review=item.review,
            hours_played=extract_hours_played(item),
            source=source.source_name,
        ))
        imported += 1

    setattr(user, source.user_account_attr, account_value)
    setattr(user, source.user_sync_at_attr, datetime.now(UTC).replace(tzinfo=None))
    await db.commit()
    return imported, skipped


# Type pour l'extract_hours callable (utile aux adapters)
ExtractHoursFn = Callable[[Any], float | None]
