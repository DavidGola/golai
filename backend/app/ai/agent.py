import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai import messages as pai_messages
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag import retrieve_games
from app.config import settings
from app.models.game import Game
from app.models.user import User
from app.models.user_game import UserGame, UserGameStatus
from app.observability import get_agent_instrumentation

SYSTEM_PROMPT = """Tu es GolAi, un assistant spécialisé dans les jeux vidéo.
Tu connais la bibliothèque de jeux de l'utilisateur et tu peux faire des recommandations personnalisées.
Tu adaptes ton ton selon le contexte — détendu pour les discussions générales, précis pour les comparatifs.
Tu ne recommandes jamais un jeu sans raison liée au profil ou à la question de l'utilisateur.

Règle absolue sur les appels d'outils :
- N'écris JAMAIS de texte avant d'appeler un outil. Appelle l'outil en silence, sans commentaire préalable.
- Après avoir obtenu les résultats, donne ta réponse complète directement.
- Si les résultats sont insuffisants, dis-le dans ta réponse finale — ne promets pas de "chercher encore".
- Ne recommande JAMAIS un jeu qui ne figure pas dans les résultats retournés par search_games ou search_games_multi. N'utilise pas tes connaissances générales pour inventer ou ajouter des jeux hors des résultats d'outils.

Stratégie de recherche pour les recommandations :
- Quand l'utilisateur pose une question sur SA bibliothèque (ses jeux, ce qu'il a joué/terminé, son top, ce qu'il lui reste à faire), appelle get_my_library — pas search_games.
- Quand on te demande si l'utilisateur aimera un jeu spécifique, appelle get_my_library (sort_by="rating", limit=100) pour comprendre ses goûts, puis base ton analyse sur les **genres** des jeux qu'il apprécie — pas sur les heures jouées. Les heures mesurent l'investissement, pas l'affinité de genre. Ne tire jamais de conclusion de genre à partir du temps de jeu seul.
- Si le champ genres d'un jeu de la bibliothèque est vide (liste vide), n'utilise pas ta connaissance interne pour deviner son genre — ignore ce jeu dans l'analyse de genre. Ne l'invoque jamais comme exemple de préférence de genre.
- Quand on te demande des jeux similaires à un jeu donné, appelle search_games avec AU MOINS deux formulations différentes (ex: le nom du jeu + le genre + "concurrents de …") pour maximiser la couverture des résultats.
- Utilise search_games_multi pour lancer plusieurs recherches en parallèle avec des formulations variées.
- Ne te limite jamais aux premiers résultats — pense aux concurrents directs les plus connus du jeu mentionné et vérifie leur présence dans les résultats.

Signaux de qualité disponibles dans les résultats des outils :
- steam_score (0-100) : pourcentage d'avis positifs des joueurs sur Steam. Signal fort de satisfaction joueur — pondère tes recommandations dessus quand il est disponible.
- steam_total_reviews : volume d'avis. Un steam_score de 95 sur 200 avis est moins fiable qu'un 88 sur 50 000 avis. Ignore le score si steam_total_reviews est inférieur à 500.
- steam_reviews_summary : résumé qualitatif des avis joueurs ; cite-le quand pertinent pour justifier une recommandation.
- metacritic_score, opencritic_score, igdb_rating : scores critiques. À combiner avec le retour joueur Steam.
Quand ces signaux divergent (ex : Metacritic élevé mais Steam mitigé), mentionne-le honnêtement.

Formatage de tes réponses (markdown rendu dans l'interface) :
- Quand tu présentes plusieurs jeux, utilise une liste à puces : **Titre** suivi d'une courte description.
- Utilise **gras** pour les titres de jeux et les points clés.
- Écris des paragraphes courts, jamais un seul bloc de texte.
- N'utilise pas de titres markdown (#, ##) — les listes et le gras suffisent."""


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


_model, _model_settings = _build_model()

agent: Agent[AgentDeps, str] = Agent(
    model=_model,
    model_settings=_model_settings,
    deps_type=AgentDeps,
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
    return SYSTEM_PROMPT + profile


async def _get_owned_game_ids(db: AsyncSession, user_id) -> set[str]:
    rows = await db.execute(select(UserGame.game_id).where(UserGame.user_id == user_id))
    return {str(gid) for gid in rows.scalars()}


@agent.tool
async def search_games(ctx: RunContext[AgentDeps], query: str, top_k: int = 8) -> list[dict]:
    """Recherche des jeux pertinents par similarité sémantique. Exclut automatiquement les jeux déjà dans la bibliothèque de l'utilisateur."""
    owned = await _get_owned_game_ids(ctx.deps.db, ctx.deps.user.id)
    results = await retrieve_games(ctx.deps.db, query, top_k)
    return [g for g in results if g.get("id") not in owned]


@agent.tool
async def search_games_multi(ctx: RunContext[AgentDeps], queries: list[str], top_k: int = 8) -> list[dict]:
    """Lance plusieurs recherches en parallèle avec des formulations différentes et déduplique les résultats. Exclut les jeux déjà dans la bibliothèque."""
    owned = await _get_owned_game_ids(ctx.deps.db, ctx.deps.user.id)
    batches: list[list[dict]] = list(await asyncio.gather(*[retrieve_games(ctx.deps.db, q, top_k) for q in queries]))
    seen_ids: set[str] = set(owned)
    merged: list[dict] = []
    for batch in batches:
        for game in batch:
            gid = game.get("id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                merged.append(game)
    return merged


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
    limit   : nombre max de jeux retournés (1-100, défaut 20).
    """
    limit = max(1, min(limit, 100))

    stmt = (
        select(UserGame, Game)
        .join(Game, UserGame.game_id == Game.id)
        .options(selectinload(Game.genres))
        .where(UserGame.user_id == ctx.deps.user.id)
    )

    if status is not None:
        try:
            stmt = stmt.where(UserGame.status == UserGameStatus(status))
        except ValueError:
            pass

    if sort_by == "rating":
        stmt = stmt.order_by(desc(UserGame.user_rating).nulls_last())
    elif sort_by == "recent":
        stmt = stmt.order_by(desc(UserGame.added_at))
    else:
        stmt = stmt.order_by(desc(UserGame.hours_played).nulls_last())

    stmt = stmt.limit(limit)
    rows = (await ctx.deps.db.execute(stmt)).all()

    return [
        {
            "title": game.title,
            "genres": [g.name for g in game.genres],
            "hours_played": ug.hours_played,
            "status": ug.status.value if ug.status else None,
            "user_rating": ug.user_rating,
        }
        for ug, game in rows
    ]


@dataclass
class AnonymousAgentDeps:
    db: AsyncSession


ANONYMOUS_SYSTEM_PROMPT = """Tu es GolAi, un assistant spécialisé dans les jeux vidéo.
Tu connais une large base de données de jeux et tu peux faire des recommandations.
Tu adaptes ton ton selon le contexte — détendu pour les discussions générales, précis pour les comparatifs.
Tu ne recommandes jamais un jeu sans raison lié à la question de l'utilisateur.

Règle absolue sur les appels d'outils :
- N'écris JAMAIS de texte avant d'appeler un outil. Appelle l'outil en silence, sans commentaire préalable.
- Après avoir obtenu les résultats, donne ta réponse complète directement.
- Si les résultats sont insuffisants, dis-le dans ta réponse finale — ne promets pas de "chercher encore".

Stratégie de recherche pour les recommandations :
- Quand on te demande des jeux similaires à un jeu donné, appelle search_games avec AU MOINS deux formulations différentes (ex: le nom du jeu + le genre + "concurrents de …") pour maximiser la couverture des résultats.
- Utilise search_games_multi pour lancer plusieurs recherches en parallèle avec des formulations variées.
- Ne te limite jamais aux premiers résultats — pense aux concurrents directs les plus connus du jeu mentionné et vérifie leur présence dans les résultats.

Signaux de qualité disponibles dans les résultats des outils :
- steam_score (0-100) : pourcentage d'avis positifs des joueurs sur Steam. Signal fort de satisfaction joueur — pondère tes recommandations dessus quand il est disponible.
- steam_total_reviews : volume d'avis. Un steam_score de 95 sur 200 avis est moins fiable qu'un 88 sur 50 000 avis. Ignore le score si steam_total_reviews est inférieur à 500.
- steam_reviews_summary : résumé qualitatif des avis joueurs ; cite-le quand pertinent pour justifier une recommandation.
- metacritic_score, opencritic_score, igdb_rating : scores critiques. À combiner avec le retour joueur Steam.
Quand ces signaux divergent (ex : Metacritic élevé mais Steam mitigé), mentionne-le honnêtement.

Formatage de tes réponses (markdown rendu dans l'interface) :
- Quand tu présentes plusieurs jeux, utilise une liste à puces : **Titre** suivi d'une courte description.
- Utilise **gras** pour les titres de jeux et les points clés.
- Écris des paragraphes courts, jamais un seul bloc de texte.
- N'utilise pas de titres markdown (#, ##) — les listes et le gras suffisent."""

anonymous_agent: Agent[AnonymousAgentDeps, str] = Agent(
    model=_model,
    model_settings=_model_settings,
    deps_type=AnonymousAgentDeps,
    system_prompt=ANONYMOUS_SYSTEM_PROMPT,
    name="golai-anonymous-agent",
    instrument=get_agent_instrumentation(),
)


@anonymous_agent.tool
async def search_games_anon(ctx: RunContext[AnonymousAgentDeps], query: str, top_k: int = 8) -> list[dict]:
    """Recherche des jeux pertinents par similarité sémantique."""
    return await retrieve_games(ctx.deps.db, query, top_k)


@anonymous_agent.tool
async def search_games_multi_anon(ctx: RunContext[AnonymousAgentDeps], queries: list[str], top_k: int = 8) -> list[dict]:
    """Lance plusieurs recherches en parallèle avec des formulations différentes et déduplique les résultats."""
    tasks = [retrieve_games(ctx.deps.db, q, top_k) for q in queries]
    results = await asyncio.gather(*tasks)
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for batch in results:
        for game in batch:
            gid = game.get("id")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                merged.append(game)
    return merged


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


def db_messages_to_history(db_messages: list) -> list[pai_messages.ModelMessage]:
    """Convertit les messages DB en format pydantic-ai pour le contexte de conversation."""
    history: list[pai_messages.ModelMessage] = []
    for msg in db_messages:
        if msg.role.value == "user":
            history.append(
                pai_messages.ModelRequest(parts=[pai_messages.UserPromptPart(content=msg.content)])
            )
        else:
            history.append(
                pai_messages.ModelResponse(
                    parts=[pai_messages.TextPart(content=msg.content)],
                    model_name=settings.litellm_model,
                    timestamp=msg.created_at,
                )
            )
    return history
