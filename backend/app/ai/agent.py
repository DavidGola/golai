import asyncio
import uuid
from dataclasses import dataclass
from typing import Protocol

from pydantic_ai import Agent, RunContext
from pydantic_ai import messages as pai_messages
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.proposals as proposals_service
import app.services.user_games as ug_service
from app.ai.prompts import build_auth_system_prompt, build_anonymous_system_prompt
from app.ai.rag import retrieve_games
from app.services.edition_collapse import collapse_editions
from app.services.library import played_game_ids
from app.config import settings
from app.models.user import User
from app.models.user_game import UserGameStatus
from app.observability import get_agent_instrumentation
from app.schemas.proposals import (
    AddToLibraryDraft,
    ChangeStatusDraft,
    RemoveFromLibraryDraft,
    SetRatingDraft,
)


class HasDb(Protocol):
    """Contract structurel : tout deps avec une AsyncSession `db` peut utiliser
    les tools du search_toolset partagé. Implémenté par AgentDeps et
    AnonymousAgentDeps via structural typing (pas d'héritage)."""
    db: AsyncSession


def _build_model() -> tuple[Model, ModelSettings | None]:
    """
    Crée le modèle pydantic-ai selon LITELLM_MODEL (format provider/model-name).

    - anthropic/...  → AnthropicModel avec prompt caching activé (ANTHROPIC_API_KEY requis)
    - openai/...     → OpenAIChatModel — caching automatique côté provider (OPENAI_API_KEY requis)
    - gemini/...     → GoogleModel via Gemini API (GEMINI_API_KEY requis)
    - openrouter/... → OpenAIChatModel via LiteLLMProvider (OPENROUTER_API_KEY requis)
    - zai/...        → OpenAIChatModel via LiteLLMProvider (GLM_API_KEY requis)
    - autre          → OpenAIChatModel via LiteLLMProvider (LITELLM_API_BASE + clé provider si configurée)

    Retourne (model, model_settings). model_settings vaut None quand le caching
    est géré automatiquement par le provider sans configuration explicite.

    Note : OpenAIChatModel ne veut pas toujours dire "appel à OpenAI".
    C'est aussi le client pydantic-ai utilisé pour les APIs compatibles OpenAI,
    comme OpenRouter ou Z.ai/GLM via LiteLLMProvider + api_base dédié.
    """
    model_str = settings.litellm_model
    provider, model_name = model_str.split("/", 1) if "/" in model_str else ("anthropic", model_str)

    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
        from pydantic_ai.providers.anthropic import AnthropicProvider
        model = AnthropicModel(
            model_name,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
        )
        # Cache le system prompt statique + tool definitions (total > 1024 tokens, seuil Anthropic).
        # TTL 5 min : refreshed à chaque hit → chaud tant que la session est active.
        model_settings = AnthropicModelSettings(
            anthropic_cache_instructions=True,
            anthropic_cache_tool_definitions=True,
        )
        return model, model_settings

    if provider == "openai":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(api_key=settings.openai_api_key or None),
        ), None

    if provider == "gemini":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
        return GoogleModel(
            model_name,
            provider=GoogleProvider(api_key=settings.gemini_api_key or None),
        ), None

    if provider == "openrouter":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.litellm import LiteLLMProvider
        # OpenRouter expose une API compatible OpenAI. On utilise donc
        # OpenAIChatModel comme enveloppe protocolaire, mais les requêtes vont
        # bien vers OpenRouter via api_base + OPENROUTER_API_KEY.
        return OpenAIChatModel(
            model_name,
            provider=LiteLLMProvider(
                api_base=settings.litellm_api_base or "https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key or None,
            ),
        ), None

    if provider in {"zai", "glm"}:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.litellm import LiteLLMProvider
        # Z.ai expose une API compatible OpenAI. L'API attend le nom réel du
        # modèle ("glm-5.1"), pas le préfixe LiteLLM ("zai/glm-5.1").
        return OpenAIChatModel(
            model_name,
            provider=LiteLLMProvider(
                api_base=settings.litellm_api_base or "https://api.z.ai/api/paas/v4",
                api_key=settings.glm_api_key or None,
            ),
        ), None

    # Tout autre provider (meta-llama, mistral, groq…) via proxy LiteLLM
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.litellm import LiteLLMProvider
    provider_api_keys = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "gemini": settings.gemini_api_key,
        "openrouter": settings.openrouter_api_key,
        "zai": settings.glm_api_key,
        "glm": settings.glm_api_key,
    }
    return OpenAIChatModel(
        model_str,
        provider=LiteLLMProvider(
            api_base=settings.litellm_api_base or None,
            api_key=provider_api_keys.get(provider) or None,
        ),
    ), None


@dataclass
class AgentDeps:
    db: AsyncSession
    user: User


@dataclass
class AnonymousAgentDeps:
    db: AsyncSession


# ─── Toolset catalogue : découverte (auth + anonyme) ────────────────────────
# En auth, exclut automatiquement les jeux "joués" (hors Backlog).
# En anonyme, aucun filtre (pas de Library).
catalog_toolset: FunctionToolset[HasDb] = FunctionToolset()


@catalog_toolset.tool
async def search_catalog(ctx: RunContext[HasDb], query: str, top_k: int = settings.rag_top_k, prefer_popular: bool = True) -> list[dict]:
    """Recherche des jeux dans le catalogue pour la découverte. En auth, exclut automatiquement les jeux déjà joués (>= 2h ou completed/dropped). Pour comparer/discuter des jeux déjà possédés, utilise search_owned_games.
    prefer_popular=True (défaut) : privilégie les jeux connus à pertinence comparable. Passe False uniquement sur demande explicite d'obscur (surprends-moi, pépites méconnues, indé pointu)."""
    exclude_ids = None
    if isinstance(ctx.deps, AgentDeps):
        played = await played_game_ids(ctx.deps.db, ctx.deps.user.id)
        exclude_ids = played if played else None
    alpha = settings.rag_notoriety_alpha if prefer_popular else 0.0
    rows = await retrieve_games(ctx.deps.db, query, top_k, exclude_ids=exclude_ids, alpha=alpha)
    return collapse_editions(rows)


@catalog_toolset.tool
async def search_catalog_multi(ctx: RunContext[HasDb], queries: list[str], top_k: int = settings.rag_top_k, prefer_popular: bool = True) -> list[dict]:
    """Lance plusieurs recherches catalogue en parallèle avec des formulations différentes et déduplique les résultats. Même filtre Backlog que search_catalog.
    prefer_popular=True (défaut) : privilégie les jeux connus à pertinence comparable. Passe False uniquement sur demande explicite d'obscur."""
    exclude_ids = None
    if isinstance(ctx.deps, AgentDeps):
        played = await played_game_ids(ctx.deps.db, ctx.deps.user.id)
        exclude_ids = played if played else None
    alpha = settings.rag_notoriety_alpha if prefer_popular else 0.0
    batches: list[list[dict]] = list(
        await asyncio.gather(*[retrieve_games(ctx.deps.db, q, top_k, exclude_ids=exclude_ids, alpha=alpha) for q in queries])
    )
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for batch in batches:
        for game in batch:
            gid = game.get("id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                merged.append(game)
    return collapse_editions(merged)


# ─── Toolset owned : recherche sans filtre Library (auth uniquement) ─────────
owned_toolset: FunctionToolset[AgentDeps] = FunctionToolset()


@owned_toolset.tool
async def search_owned_games(ctx: RunContext[AgentDeps], query: str, top_k: int = settings.rag_top_k) -> list[dict]:
    """Recherche des jeux sans filtre Library. À utiliser uniquement si l'utilisateur veut explicitement comparer ou parler d'un jeu qu'il possède déjà."""
    return await retrieve_games(ctx.deps.db, query, top_k)


_model, _model_settings = _build_model()

agent: Agent[AgentDeps, str] = Agent(
    model=_model,
    model_settings=_model_settings,
    deps_type=AgentDeps,
    toolsets=[catalog_toolset, owned_toolset],
    name="golai-auth-agent",
    instrument=get_agent_instrumentation(),
)


@agent.system_prompt
async def build_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    user = ctx.deps.user
    genres = ", ".join(g.name for g in user.favorite_genres) if user.favorite_genres else "non spécifiés"
    criteria = ", ".join(c.name for c in user.important_criteria) if user.important_criteria else "non spécifiés"
    profile = (
        f"\nProfil utilisateur :"
        f"\n- Nom : {user.username}"
        f"\n- Préférence de durée : {user.preferred_playtime or 'non spécifiée'}"
        f"\n- Genres favoris : {genres}"
        f"\n- Critères importants : {criteria}"
    )
    return build_auth_system_prompt() + profile


@agent.tool
async def get_my_library(
    ctx: RunContext[AgentDeps],
    sort_by: str = "playtime",
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Récupère la bibliothèque personnelle de l'utilisateur.

    sort_by : "playtime" (heures jouées desc), "rating" (note user desc), "recent" (ajout desc).
    status  : filtre optionnel — "completed", "todo", "dropped", "not_started".
    limit   : nombre max de jeux retournés (1-100, défaut 50).
    """
    bounded_limit = max(1, min(limit, 100))

    parsed_status: UserGameStatus | None = None
    if status is not None:
        try:
            parsed_status = UserGameStatus(status)
        except ValueError:
            parsed_status = None

    normalized_sort: ug_service.LibrarySortBy
    if sort_by == "rating":
        normalized_sort = "rating"
    elif sort_by == "recent":
        normalized_sort = "recent"
    else:
        normalized_sort = "playtime"

    entries = await ug_service.list_library(
        ctx.deps.db,
        ctx.deps.user.id,
        status=parsed_status,
        sort_by=normalized_sort,
        limit=bounded_limit,
    )

    return [
        {
            "user_game_id": str(ug.id),
            "title": ug.game.title,
            "genres": [g.name for g in ug.game.genres],
            "hours_played": ug.hours_played,
            "status": ug.status.value if ug.status else None,
            "user_rating": ug.user_rating,
        }
        for ug in entries
    ]


# ─── Tools propose_* — fines couches vers proposals_service ──────────────────
# Les tools renvoient un Draft sérialisé (model_dump) ou un dict d'erreur.
# Ne génèrent JAMAIS d'id : l'id naît au persist (services/proposals.persist_drafts).
# Aucun SQL ici — tout passe par proposals_service.draft_*.


def _draft_to_tool_result(draft: AddToLibraryDraft | ChangeStatusDraft | SetRatingDraft | RemoveFromLibraryDraft) -> dict:
    """Sérialise un Draft pour retour au LLM ET stream.py (qui détecte 'action_type' pour relayer)."""
    return draft.model_dump(mode="json")


def _parse_uuid_or_none(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


@agent.tool
async def propose_add_to_library(
    ctx: RunContext[AgentDeps],
    game_id: str,
    status: str | None = None,
    rating: int | None = None,
    review: str | None = None,
) -> dict:
    """Propose d'ajouter un jeu à la bibliothèque, avec une note et/ou un avis optionnels.
    Ne modifie PAS la DB — crée une carte de confirmation.
    game_id : provient d'un résultat search_catalog. status : "todo", "not_started", "completed", "dropped".
    rating : entier 1-10 (optionnel). review : texte libre (optionnel).
    Retourne une erreur si le jeu est déjà dans la bibliothèque."""
    gid = _parse_uuid_or_none(game_id)
    if gid is None:
        return {"error": "invalid_game_id"}

    draft_or_error = await proposals_service.draft_add_to_library(
        ctx.deps.db,
        ctx.deps.user.id,
        game_id=gid,
        status_value=status,
        rating=rating,
        review=review,
    )
    if isinstance(draft_or_error, dict):
        return draft_or_error
    return _draft_to_tool_result(draft_or_error)


@agent.tool
async def propose_change_status(
    ctx: RunContext[AgentDeps],
    new_status: str,
    user_game_id: str | None = None,
    game_id: str | None = None,
) -> dict:
    """Propose de changer le statut d'un jeu de la bibliothèque. Ne modifie PAS la DB.
    Fournir SOIT user_game_id SOIT game_id (mais pas les deux).
    user_game_id : l'id du UserGame (obtenu via get_my_library).
    game_id : l'id du jeu dans le catalogue (ex: depuis search_catalog ou annotation d'historique).
    new_status : "todo", "not_started", "completed", "dropped"."""
    ugid = _parse_uuid_or_none(user_game_id)
    gid = _parse_uuid_or_none(game_id)
    if user_game_id and ugid is None:
        return {"error": "invalid_user_game_id"}
    if game_id and gid is None:
        return {"error": "invalid_game_id"}

    draft_or_error = await proposals_service.draft_change_status(
        ctx.deps.db,
        ctx.deps.user.id,
        new_status_value=new_status,
        user_game_id=ugid,
        game_id=gid,
    )
    if isinstance(draft_or_error, dict):
        return draft_or_error
    return _draft_to_tool_result(draft_or_error)


@agent.tool
async def propose_set_rating(
    ctx: RunContext[AgentDeps],
    user_game_id: str | None = None,
    game_id: str | None = None,
    rating: int | None = None,
    review: str | None = None,
) -> dict:
    """Propose de noter un jeu et/ou d'écrire une review. Ne modifie PAS la DB.
    Fournir SOIT user_game_id SOIT game_id (mais pas les deux).
    user_game_id : l'id du UserGame (obtenu via get_my_library).
    game_id : l'id du jeu dans le catalogue (ex: depuis search_catalog ou annotation d'historique).
    rating : entier 1-10. review : texte libre."""
    ugid = _parse_uuid_or_none(user_game_id)
    gid = _parse_uuid_or_none(game_id)
    if user_game_id and ugid is None:
        return {"error": "invalid_user_game_id"}
    if game_id and gid is None:
        return {"error": "invalid_game_id"}

    draft_or_error = await proposals_service.draft_set_rating(
        ctx.deps.db,
        ctx.deps.user.id,
        user_game_id=ugid,
        game_id=gid,
        rating=rating,
        review=review,
    )
    if isinstance(draft_or_error, dict):
        return draft_or_error
    return _draft_to_tool_result(draft_or_error)


@agent.tool
async def propose_remove_from_library(
    ctx: RunContext[AgentDeps],
    user_game_id: str | None = None,
    game_id: str | None = None,
) -> dict:
    """Propose de supprimer un jeu de la bibliothèque. Ne modifie PAS la DB.
    Fournir SOIT user_game_id SOIT game_id (mais pas les deux).
    user_game_id : l'id du UserGame (obtenu via get_my_library).
    game_id : l'id du jeu dans le catalogue (ex: depuis search_catalog ou annotation d'historique)."""
    ugid = _parse_uuid_or_none(user_game_id)
    gid = _parse_uuid_or_none(game_id)
    if user_game_id and ugid is None:
        return {"error": "invalid_user_game_id"}
    if game_id and gid is None:
        return {"error": "invalid_game_id"}

    draft_or_error = await proposals_service.draft_remove_from_library(
        ctx.deps.db,
        ctx.deps.user.id,
        user_game_id=ugid,
        game_id=gid,
    )
    if isinstance(draft_or_error, dict):
        return draft_or_error
    return _draft_to_tool_result(draft_or_error)


anonymous_agent: Agent[AnonymousAgentDeps, str] = Agent(
    model=_model,
    model_settings=_model_settings,
    deps_type=AnonymousAgentDeps,
    toolsets=[catalog_toolset],
    system_prompt=build_anonymous_system_prompt(),
    name="golai-anonymous-agent",
    instrument=get_agent_instrumentation(),
)


def history_dicts_to_messages(history: list) -> list[pai_messages.ModelMessage]:
    """Convertit une liste de dicts {role, content} en format pydantic-ai."""
    result: list[pai_messages.ModelMessage] = []
    for msg in history:
        if msg["role"] == "user":
            result.append(
                pai_messages.ModelRequest(parts=[pai_messages.UserPromptPart(content=msg["content"])])
            )
        else:
            result.append(
                pai_messages.ModelResponse(
                    parts=[pai_messages.TextPart(content=msg["content"])],
                    model_name=settings.litellm_model,
                )
            )
    return result


def _payload_to_tool_args(action: str, payload: dict) -> dict:
    if action == "add_to_library":
        return {
            "game_id": payload.get("game_id"),
            "status": payload.get("status"),
            "rating": payload.get("rating"),
            "review": payload.get("review"),
        }
    if action == "change_status":
        return {"user_game_id": payload.get("user_game_id"), "new_status": payload.get("new_status")}
    if action == "set_rating":
        return {
            "user_game_id": payload.get("user_game_id"),
            "rating": payload.get("rating"),
            "review": payload.get("review"),
        }
    if action == "remove_from_library":
        return {"user_game_id": payload.get("user_game_id")}
    return {}


def db_messages_to_history(db_messages: list) -> list[pai_messages.ModelMessage]:
    """Convertit les messages DB en format pydantic-ai pour le contexte de conversation."""
    history: list[pai_messages.ModelMessage] = []
    for msg in db_messages:
        if msg.role.value == "user":
            history.append(
                pai_messages.ModelRequest(parts=[pai_messages.UserPromptPart(content=msg.content)])
            )
            continue

        response_parts: list = []
        if msg.content:
            response_parts.append(pai_messages.TextPart(content=msg.content))

        tool_returns: list[pai_messages.ToolReturnPart] = []
        for p in (getattr(msg, "proposals", None) or []):
            tool_name = f"propose_{p.action_type.value}"
            tool_call_id = f"hist_{p.id.hex[:16]}"
            args = _payload_to_tool_args(p.action_type.value, p.payload)
            response_parts.append(pai_messages.ToolCallPart(
                tool_name=tool_name,
                args=args,
                tool_call_id=tool_call_id,
            ))
            tool_returns.append(pai_messages.ToolReturnPart(
                tool_name=tool_name,
                content={
                    "proposal_id": str(p.id),
                    "action_type": p.action_type.value,
                    "state": p.state.value,
                    **p.payload,
                },
                tool_call_id=tool_call_id,
            ))

        history.append(
            pai_messages.ModelResponse(
                parts=response_parts,
                model_name=settings.litellm_model,
                timestamp=msg.created_at,
            )
        )
        if tool_returns:
            history.append(pai_messages.ModelRequest(parts=list(tool_returns)))
    return history
