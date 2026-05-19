"""
Tests unitaires pour collapse_editions.
Fonction pure — aucune fixture DB requise.
"""
from datetime import datetime

import pytest

from app.services.edition_collapse import collapse_editions


def _game(
    id_: str,
    edition_type: str = "original",
    parent_game_id: str | None = None,
    release_date: datetime | None = None,
) -> dict:
    return {
        "id": id_,
        "edition_type": edition_type,
        "parent_game_id": parent_game_id,
        "release_date": release_date,
    }


def ids(result: list[dict]) -> list[str]:
    return [r["id"] for r in result]


# T1
def test_original_alone():
    rows = [_game("a")]
    assert ids(collapse_editions(rows)) == ["a"]


# T2
def test_original_plus_remaster_returns_remaster():
    rows = [
        _game("a", "original", release_date=datetime(2012, 1, 1)),
        _game("b", "remaster", parent_game_id="a", release_date=datetime(2018, 1, 1)),
    ]
    assert ids(collapse_editions(rows)) == ["b"]


# T3
def test_original_plus_expanded_returns_expanded():
    rows = [
        _game("a", "original", release_date=datetime(2011, 1, 1)),
        _game("b", "expanded", parent_game_id="a", release_date=datetime(2013, 1, 1)),
    ]
    assert ids(collapse_editions(rows)) == ["b"]


# T4
def test_original_plus_remake_both_coexist():
    rows = [
        _game("a", "original", release_date=datetime(1998, 1, 1)),
        _game("b", "remake", parent_game_id="a", release_date=datetime(2019, 1, 1)),
    ]
    assert ids(collapse_editions(rows)) == ["a", "b"]


# T5
def test_original_plus_remake_plus_remaster_returns_remaster_and_remake():
    rows = [
        _game("a", "original", release_date=datetime(2012, 1, 1)),
        _game("b", "remake", parent_game_id="a", release_date=datetime(2018, 1, 1)),
        _game("c", "remaster", parent_game_id="a", release_date=datetime(2022, 1, 1)),
    ]
    result_ids = ids(collapse_editions(rows))
    assert "a" not in result_ids
    assert "b" in result_ids
    assert "c" in result_ids


# T6
def test_two_independent_groups_collapsed_separately():
    rows = [
        _game("a1", "original", release_date=datetime(2012, 1, 1)),
        _game("a2", "remaster", parent_game_id="a1", release_date=datetime(2018, 1, 1)),
        _game("b1", "original", release_date=datetime(2011, 1, 1)),
        _game("b2", "remaster", parent_game_id="b1", release_date=datetime(2016, 1, 1)),
    ]
    assert ids(collapse_editions(rows)) == ["a2", "b2"]


# T7
def test_orphan_remaster_without_original_in_results():
    rows = [_game("b", "remaster", parent_game_id="a", release_date=datetime(2018, 1, 1))]
    assert ids(collapse_editions(rows)) == ["b"]


# T8
def test_original_without_descendant():
    rows = [_game("a", "original", release_date=datetime(2020, 1, 1))]
    assert ids(collapse_editions(rows)) == ["a"]


# T9
def test_rag_order_preserved_after_collapse():
    rows = [
        _game("sky", "original", release_date=datetime(2011, 1, 1)),
        _game("dark", "original", release_date=datetime(2012, 1, 1)),
        _game("sky_se", "expanded", parent_game_id="sky", release_date=datetime(2016, 1, 1)),
        _game("dark_r", "remaster", parent_game_id="dark", release_date=datetime(2018, 1, 1)),
        _game("re2", "original", release_date=datetime(2020, 1, 1)),
    ]
    result_ids = ids(collapse_editions(rows))
    assert result_ids.index("sky_se") < result_ids.index("dark_r")
    assert result_ids.index("dark_r") < result_ids.index("re2")
