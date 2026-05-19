"""
Tests d'invariants de sécurité pour l'agent anonyme.

Garantit que l'agent anonyme n'expose AUCUN tool capable de muter
ou de lire la Library d'un user. Si ces tests cassent, c'est qu'un
nouveau tool a été ajouté dans le mauvais agent — risque de fuite
de données ou de mutation non-autorisée.

Référence : ADR-0015 (mutations Library via Proposal confirmée).
"""

import pytest

from app.ai.agent import agent, anonymous_agent


@pytest.fixture
def auth_tool_names() -> set[str]:
    """Tous les tools exposés à l'agent auth (toolsets partagés inclus)."""
    return set(agent._function_toolset.tools.keys()) | {
        t for ts in agent._user_toolsets for t in ts.tools.keys()
    }


@pytest.fixture
def anon_tool_names() -> set[str]:
    """Tous les tools exposés à l'agent anonyme (toolsets partagés inclus)."""
    return set(anonymous_agent._function_toolset.tools.keys()) | {
        t for ts in anonymous_agent._user_toolsets for t in ts.tools.keys()
    }


def test_anonymous_agent_has_no_proposal_tools(anon_tool_names):
    """L'agent anonyme ne doit JAMAIS exposer de tools propose_*.

    Si ce test casse, quelqu'un a accidentellement greffé une mutation
    Library sur l'agent anonyme — violation directe d'ADR-0015.
    """
    propose_tools = {n for n in anon_tool_names if n.startswith("propose_")}
    assert not propose_tools, (
        f"L'agent anonyme expose des tools propose_* : {propose_tools}. "
        "Aucun anonyme ne peut posséder de Library, donc aucune Proposal "
        "ne devrait être possible."
    )


def test_anonymous_agent_cannot_read_library(anon_tool_names):
    """L'agent anonyme ne doit pas exposer get_my_library.

    Un anonyme n'a pas de Library, donc ce tool n'a pas de sens —
    et il révélerait que la deps.user n'existe pas (crash runtime,
    mais surtout fuite de l'architecture interne).
    """
    assert "get_my_library" not in anon_tool_names


def test_anonymous_agent_only_exposes_catalog_tools(anon_tool_names):
    """Whitelist explicite : seuls les tools catalogue sont autorisés en anonyme.

    Si un nouveau tool est ajouté à l'agent anonyme, il doit explicitement
    être ajouté à cette liste — sinon le test casse et le dev doit justifier.
    """
    allowed = {"search_catalog", "search_catalog_multi"}
    extra = anon_tool_names - allowed
    assert not extra, (
        f"Tools non whitelistés sur l'agent anonyme : {extra}. "
        f"Ajoute-les à `allowed` après revue sécurité."
    )


def test_catalog_tools_are_shared_with_auth(auth_tool_names, anon_tool_names):
    """search_catalog et search_catalog_multi doivent exister sur les deux agents
    (catalog_toolset partagé). Garantit qu'on ne duplique pas accidentellement."""
    assert "search_catalog" in auth_tool_names
    assert "search_catalog" in anon_tool_names
    assert "search_catalog_multi" in auth_tool_names
    assert "search_catalog_multi" in anon_tool_names


def test_auth_agent_exposes_all_library_tools(auth_tool_names):
    """L'agent auth doit avoir l'ensemble complet : catalog + owned + library read + 4 propose_*."""
    expected = {
        "search_catalog",
        "search_catalog_multi",
        "search_owned_games",
        "get_my_library",
        "propose_add_to_library",
        "propose_change_status",
        "propose_set_rating",
        "propose_remove_from_library",
    }
    missing = expected - auth_tool_names
    assert not missing, f"Tools manquants sur l'agent auth : {missing}"
