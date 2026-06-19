"""
Tests unitaires pour guardrails.py — M4 find_ungrounded_titles + M5 build_allowlist.
Fonctions pures, pas de DB, pas de I/O.
"""
from app.ai.guardrails import find_ungrounded_titles, build_allowlist


# ─── M4 : find_ungrounded_titles ─────────────────────────────────────────────


# T1 — tracer bullet : titre gras absent de l'allowlist est retourné
def test_find_ungrounded_bold_title_not_in_allowlist():
    result = find_ungrounded_titles("Je recommande **God of War**.", set())
    assert result == ["God of War"]


# T2 — titre gras présent dans l'allowlist → ignoré
def test_find_ungrounded_title_in_allowlist_is_grounded():
    result = find_ungrounded_titles("**God of War**", {"God of War"})
    assert result == []


# T3 — matching tolérant : nom court ↔ nom complet (substring)
def test_find_ungrounded_short_name_matches_full_allowlist_entry():
    # "Sekiro" est substring de "Sekiro: Shadows Die Twice" → fondé
    result = find_ungrounded_titles("**Sekiro**", {"Sekiro: Shadows Die Twice"})
    assert result == []


def test_find_ungrounded_full_name_matches_short_allowlist_entry():
    # "Sekiro: Shadows Die Twice" contient "Sekiro" → fondé
    result = find_ungrounded_titles("**Sekiro: Shadows Die Twice**", {"Sekiro"})
    assert result == []


# T4 — réponse sans titre gras → liste vide (pas de retry sur tours de cadrage)
def test_find_ungrounded_no_bold_titles_returns_empty():
    result = find_ungrounded_titles(
        "Bonsoir, comment puis-je t'aider aujourd'hui ?", {"God of War"}
    )
    assert result == []


# T5 — normalisation : différences de casse ignorées
def test_find_ungrounded_case_insensitive_match():
    result = find_ungrounded_titles("**god of war**", {"God of War"})
    assert result == []


# T6 — plusieurs titres : un fondé, un non-fondé → seul le non-fondé est retourné
def test_find_ungrounded_mixed_titles():
    result = find_ungrounded_titles(
        "Essaie **God of War** et **Hollow Knight**.",
        {"God of War"},
    )
    assert result == ["Hollow Knight"]


# ─── M5 : build_allowlist ────────────────────────────────────────────────────


# T7 — titre depuis search_results est dans l'allowlist
def test_build_allowlist_includes_search_result_titles():
    allowlist = build_allowlist(
        search_results=[{"id": "abc", "title": "God of War"}],
        library_titles=[],
        user_message="",
    )
    assert "God of War" in allowlist


# T8 — titre de la Library est dans l'allowlist
def test_build_allowlist_includes_library_titles():
    allowlist = build_allowlist(
        search_results=[],
        library_titles=["Hollow Knight"],
        user_message="",
    )
    assert "Hollow Knight" in allowlist


# T9 — titre tapé par le user est dans l'allowlist (via matching substring)
def test_build_allowlist_user_message_grounds_typed_title():
    allowlist = build_allowlist(
        search_results=[],
        library_titles=[],
        user_message="Je veux jouer à Hades",
    )
    # Le titre **Hades** doit être fondé via substring match sur le message
    ungrounded = find_ungrounded_titles("**Hades**", allowlist)
    assert ungrounded == []


# T10 — union des 3 sources
def test_build_allowlist_union_of_all_sources():
    allowlist = build_allowlist(
        search_results=[{"title": "Elden Ring"}],
        library_titles=["Dark Souls"],
        user_message="Parle-moi de Bloodborne",
    )
    assert "Elden Ring" in allowlist
    assert "Dark Souls" in allowlist
    # Bloodborne est dans le message → doit grounder **Bloodborne**
    ungrounded = find_ungrounded_titles("**Bloodborne**", allowlist)
    assert ungrounded == []
