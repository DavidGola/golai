"""Tests d'invariants du service générique library_import.

Les tests par source (PSN/Xbox) couvrent déjà le flow end-to-end avec mocks.
Ce fichier teste les morceaux orthogonaux : helper suggest_status, contrat
du Protocol, et un cas générique avec un FakeSource pour vérifier que tout
adapter implémentant le Protocol fonctionne.
"""
from typing import Any

import pytest
from unittest.mock import patch

from app.models.game import Game
from app.models.user_game import UserGameStatus
from app.services.library_import import (
    ExternalOwnedGame,
    LibraryImportSource,
    build_preview_generic,
    suggest_status_from_completion_pct,
)


# ─── Helper suggest_status_from_completion_pct ───────────────────────────────


def test_suggest_status_none_pct_returns_none():
    assert suggest_status_from_completion_pct(None) is None


def test_suggest_status_100_completed():
    assert suggest_status_from_completion_pct(100) == UserGameStatus.completed


def test_suggest_status_partial_todo():
    assert suggest_status_from_completion_pct(50) == UserGameStatus.todo
    assert suggest_status_from_completion_pct(1) == UserGameStatus.todo


def test_suggest_status_zero_not_started():
    assert suggest_status_from_completion_pct(0) == UserGameStatus.not_started


# ─── Adapter de test : prouve que le Protocol est implémentable ─────────────
# Vérifie que l'orchestration générique marche pour n'importe quelle source
# correctement implémentée (régression : si un changement casse le contrat,
# ce test casse avant les tests par source).


class _FakeSource:
    """Source fictive pour tester le service générique sans dépendre des
    schemas/services Steam/PSN/Xbox spécifiques."""
    source_name = "fake"
    use_fuzzy_title_match = False
    # On réutilise la colonne psn_id pour stocker l'identifiant fictif —
    # évite d'ajouter une colonne au schéma juste pour le test.
    user_account_attr = "psn_online_id"
    user_sync_at_attr = "last_psn_sync_at"
    game_source_id_attr = "psn_id"

    def __init__(self, externals: list[ExternalOwnedGame]):
        self._externals = externals

    async def resolve_account(self, raw_input: str) -> tuple[str, str]:
        return raw_input, raw_input

    async def fetch_owned(self, account_id: Any) -> list[ExternalOwnedGame]:
        return self._externals

    def cast_source_id_for_db(self, source_id: str) -> str:
        return source_id


async def test_generic_creates_minimal_game_for_unknown_source_id(db_session, user_a):
    """L'orchestration générique doit créer un Game minimal quand le source_id
    n'existe ni en match exact ni en fuzzy."""
    externals = [
        ExternalOwnedGame(
            source_id="FAKE_XYZ",
            title="Brand New Title",
            cover_url="https://img/x.png",
            completion_pct=50,
        )
    ]
    source = _FakeSource(externals)

    items, storage_value = await build_preview_generic(db_session, user_a, "account_x", source)

    assert len(items) == 1
    assert items[0].external.source_id == "FAKE_XYZ"
    assert items[0].game.title == "Brand New Title"
    assert items[0].suggested_status == UserGameStatus.todo
    assert storage_value == "account_x"
    # Le compte n'est PAS écrit au preview
    assert user_a.psn_online_id is None


async def test_generic_uses_existing_game_when_source_id_matches(db_session, user_a):
    """Si Game.psn_id existe déjà, on ne crée PAS de doublon."""
    game = Game(title="Already in catalog", psn_id="FAKE_ABC")
    db_session.add(game)
    await db_session.commit()

    externals = [
        ExternalOwnedGame(
            source_id="FAKE_ABC",
            title="Already in catalog",
            cover_url=None,
            completion_pct=None,
        )
    ]
    source = _FakeSource(externals)

    items, _ = await build_preview_generic(db_session, user_a, "acc", source)

    assert len(items) == 1
    assert items[0].game.id == game.id  # ← le game existant, pas un nouveau


async def test_generic_empty_externals_returns_empty_tuple(db_session, user_a):
    """Library externe vide : retourne ([], storage_value) sans modifier le user."""
    source = _FakeSource([])

    items, storage_value = await build_preview_generic(db_session, user_a, "acc", source)

    assert items == []
    assert storage_value == "acc"
    # Le compte n'est PAS écrit au preview
    assert user_a.psn_online_id is None
    assert user_a.last_psn_sync_at is None


# ─── Garde-fou : le Protocol n'est pas vide ──────────────────────────────────


def test_library_import_source_protocol_required_attrs():
    """Si quelqu'un retire un attribut requis du Protocol, ce test casse —
    et oblige à mettre à jour les adapters en conséquence."""
    required_attrs = {
        "source_name",
        "use_fuzzy_title_match",
        "user_account_attr",
        "user_sync_at_attr",
        "game_source_id_attr",
    }
    required_methods = {"resolve_account", "fetch_owned", "cast_source_id_for_db"}

    actual_attrs = set(LibraryImportSource.__annotations__.keys())
    actual_methods = {name for name in dir(LibraryImportSource) if not name.startswith("_")}

    missing_attrs = required_attrs - actual_attrs
    missing_methods = required_methods - actual_methods
    assert not missing_attrs, f"Attributs manquants : {missing_attrs}"
    assert not missing_methods, f"Méthodes manquantes : {missing_methods}"
