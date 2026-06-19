"""
Tests unitaires pour rerank_by_notoriety.
Fonction pure — aucune fixture DB requise.
"""
import pytest

from app.ai.rerank import rerank_by_notoriety


def _c(id: str, similarity: float, p_steam: float | None = None, p_igdb: float | None = None) -> dict:
    return {"id": id, "similarity": similarity, "p_steam": p_steam, "p_igdb": p_igdb}


def ids(result: list[dict]) -> list[str]:
    return [r["id"] for r in result]


# T1 — tracer bullet
def test_empty_returns_empty():
    assert rerank_by_notoriety([], alpha=0.35) == []


# T2 — single candidate unchanged
def test_single_candidate_unchanged():
    c = _c("a", similarity=0.8, p_steam=0.5, p_igdb=0.6)
    assert rerank_by_notoriety([c], alpha=0.35) == [c]


# T3 — fallback 0.5 quand les deux signaux sont None
def test_fallback_notoriety_when_no_signals():
    candidates = [
        _c("a", similarity=0.9),  # p_steam=None, p_igdb=None → notoriété=0.5
        _c("b", similarity=0.5),  # idem
    ]
    # alpha=1 → seule la notoriété compte ; les deux = 0.5 → tri stable, ordre préservé
    assert ids(rerank_by_notoriety(candidates, alpha=1.0)) == ["a", "b"]


# T4 — max(p_steam, p_igdb) choisit le meilleur signal
def test_max_of_signals_used():
    candidates = [
        _c("b", similarity=0.7, p_steam=0.8, p_igdb=0.1),  # notoriété=0.8
        _c("a", similarity=0.7, p_steam=0.3, p_igdb=0.9),  # notoriété=0.9
    ]
    # alpha=1 → pure notoriété, a (0.9) > b (0.8)
    assert ids(rerank_by_notoriety(candidates, alpha=1.0))[0] == "a"


# T5 — alpha=0 → ordre sémantique pur
def test_alpha_zero_gives_semantic_order():
    candidates = [
        _c("a", similarity=0.95, p_steam=0.05, p_igdb=0.05),  # très pertinent, niche
        _c("b", similarity=0.50, p_steam=0.95, p_igdb=0.95),  # populaire, peu pertinent
    ]
    assert ids(rerank_by_notoriety(candidates, alpha=0.0)) == ["a", "b"]


# T6 — alpha=1 → ordre notoriété pur
def test_alpha_one_gives_notoriety_order():
    candidates = [
        _c("a", similarity=0.95, p_steam=0.05, p_igdb=0.05),
        _c("b", similarity=0.50, p_steam=0.95, p_igdb=0.95),
    ]
    assert ids(rerank_by_notoriety(candidates, alpha=1.0)) == ["b", "a"]


# T7 — alpha=0.35 : la notoriété départage deux candidats à pertinence égale
def test_notoriety_breaks_tie_at_alpha_035():
    candidates = [
        _c("very_relevant", similarity=0.95, p_steam=0.50, p_igdb=0.50),
        _c("popular",       similarity=0.80, p_steam=0.95, p_igdb=0.95),
        _c("niche",         similarity=0.80, p_steam=0.05, p_igdb=0.05),
        _c("least_relevant",similarity=0.50, p_steam=0.50, p_igdb=0.50),
    ]
    # popular et niche ont la même similarity=0.80 → la notoriété décide
    result = ids(rerank_by_notoriety(candidates, alpha=0.35))
    assert result.index("popular") < result.index("niche")


# T8 — exclu console (p_steam=None, igdb_rating_count élevé) obtient une notoriété haute
def test_console_exclusive_uses_igdb_signal():
    candidates = [
        _c("got",        similarity=0.75, p_steam=None, p_igdb=0.97),  # Ghost of Tsushima
        _c("niche",      similarity=0.78, p_steam=0.10, p_igdb=0.10),  # légèrement plus pertinent
        _c("popular_pc", similarity=0.60, p_steam=0.90, p_igdb=0.80),  # moins pertinent
    ]
    # got : sem_norm=(0.75-0.60)/0.18=0.833, notoriété=0.97
    # → final=0.65*0.833+0.35*0.97=0.541+0.340=0.881 (le plus haut)
    result = rerank_by_notoriety(candidates, alpha=0.35)
    assert ids(result)[0] == "got"


# T9 — normalisation min-max préserve l'ordre sémantique avec alpha=0
def test_semantic_order_preserved_multiple_candidates():
    candidates = [
        _c("a", similarity=0.9),
        _c("b", similarity=0.6),
        _c("c", similarity=0.3),
    ]
    assert ids(rerank_by_notoriety(candidates, alpha=0.0)) == ["a", "b", "c"]
