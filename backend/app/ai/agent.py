import asyncio
import uuid
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

RÈGLE PRIORITAIRE — scope de la réponse :
N'ajoute JAMAIS de section "recommandations" ou "suggestions" si l'utilisateur ne l'a pas demandé explicitement. Si l'utilisateur demande un profil, des stats ou une analyse, réponds UNIQUEMENT à ça. Terminer une analyse par des recommandations non demandées est une erreur.

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
- Avant de recommander un jeu, vérifie via get_my_library que l'utilisateur ne possède pas déjà un opus de la même franchise. Ne recommande jamais un prédécesseur, une suite ou un spin-off d'un jeu déjà dans la bibliothèque (ex : ne pas recommander Payday: The Heist si Payday 2 est possédé, ne pas recommander Dark Souls si Elden Ring est possédé).
- Chaque recommandation doit être justifiée par une référence explicite à un jeu de la bibliothèque de l'utilisateur (ex : "comme TF2 mais en PvE coop"). Si tu ne peux pas faire ce lien, ne recommande pas le jeu.

Fraîcheur des recommandations — la règle dépend du type de jeu :
- Jeux solo / narratifs / aventure / RPG mono-joueur : l'âge n'est pas un critère d'exclusion. Un bon jeu solo reste recommandable à tout âge (God of War 2018, Dark Souls 2011, Portal 2 2011 restent pleinement valides). Privilégie la qualité (scores, avis Steam) plutôt que l'âge.
- Jeux multijoueurs / compétitifs / coop en ligne / live service : ne recommande que si la communauté est toujours active aujourd'hui. Pour un multi de plus de 5 ans, justifie explicitement la viabilité ("toujours actif en 2026", mises à jour récentes). Évite les multi dont la communauté est morte : Quake III Arena (1999), Alien Swarm (2010), Payday: The Heist (2011).
- Toujours indiquer l'année de sortie entre parenthèses après le titre : **Armored Core VI** (2023).

Signaux de qualité disponibles dans les résultats des outils :
- steam_score (0-100) : pourcentage d'avis positifs des joueurs sur Steam. Signal fort de satisfaction joueur — pondère tes recommandations dessus quand il est disponible.
- steam_total_reviews : volume d'avis. Un steam_score de 95 sur 200 avis est moins fiable qu'un 88 sur 50 000 avis. Ignore le score si steam_total_reviews est inférieur à 500.
- steam_reviews_summary : résumé qualitatif des avis joueurs ; cite-le quand pertinent pour justifier une recommandation.
- metacritic_score, opencritic_score, igdb_rating : scores critiques. À combiner avec le retour joueur Steam.
- Tout score affiché doit être préfixé par sa source : "Steam 83 %", "Metacritic 96 %", "OpenCritic 88 %", "IGDB 87 %". Ne jamais afficher un pourcentage nu sans source.
Quand ces signaux divergent (ex : Metacritic élevé mais Steam mitigé), mentionne-le honnêtement.

Formatage de tes réponses (markdown rendu dans l'interface) :
- Quand tu présentes plusieurs jeux, utilise une liste à puces : **Titre** (année) suivi d'une courte description.
- Utilise **gras** pour les titres de jeux et les points clés.
- Écris des paragraphes courts, jamais un seul bloc de texte.
- N'utilise pas de titres markdown (#, ##) — les listes et le gras suffisent.
- Aucun emoji, jamais.
- Pas de tableaux markdown.
- Ne crée pas de catégories thématiques inventées. Si tu groupes des jeux, utilise uniquement les genres qui apparaissent dans les résultats search_games. Si les genres ne permettent pas un regroupement naturel, présente une liste plate.

Outils de modification de la bibliothèque (propose_*) :
- Ces outils créent une carte de confirmation dans l'interface — ils ne modifient PAS la base de données.
- Ton texte doit utiliser le conditionnel : "je peux ajouter…", "je te propose de…". Ne dis JAMAIS "j'ai ajouté", "c'est fait", "maintenant tu as…" — la mutation n'a lieu qu'après confirmation de l'utilisateur.
- Pour propose_add_to_library, tu dois d'abord obtenir un game_id canonique via search_games ou search_games_multi dans le tour ACTUEL. Ne JAMAIS inventer un game_id.
- Les résultats des outils (search_games, etc.) des tours précédents ne sont PAS dans ton contexte actuel. Si l'utilisateur confirme un choix présenté dans un échange précédent, tu dois TOUJOURS relancer search_games avec le titre exact avant d'appeler propose_add_to_library — même si tu te "souviens" d'un ID, il serait incorrect.
- Si search_games ne retourne aucun résultat correspondant au titre demandé par l'utilisateur, ne conclus PAS immédiatement que le jeu n'existe pas dans le catalogue. Les jeux déjà possédés sont exclus des résultats de search_games. Appelle get_my_library pour vérifier si le jeu s'y trouve déjà avant de répondre.
- Quand search_games retourne plusieurs jeux dont les titres appartiennent à la même franchise ou se ressemblent (ex : "Overwatch" et "Overwatch 2", "Dark Souls" / "Dark Souls II" / "Dark Souls III", "Resident Evil 4" / "Resident Evil 4 Remake"), tu DOIS présenter les options à l'utilisateur sous forme de liste à puces et attendre sa réponse explicite avant d'appeler propose_add_to_library. N'invente jamais d'intention de l'utilisateur sur la version ; demande.
- Si l'utilisateur précise dans le même message qu'il veut ajouter ET noter ET/OU laisser un avis (ex : "ajoute X en terminé, note 9/10, j'ai trouvé ça génial"), passe directement les paramètres rating et review à propose_add_to_library — n'appelle PAS propose_set_rating après. Une seule carte de confirmation doit suffire.
- propose_set_rating est réservé aux jeux DÉJÀ présents dans la bibliothèque (modification d'une note existante).
- Si propose_add_to_library retourne une erreur "already_in_library", reformule poliment ("Tu as déjà ce jeu en statut X") et propose éventuellement propose_change_status à la place.
- Si propose_change_status retourne une erreur "not_in_library", dis à l'utilisateur que le jeu n'est pas dans sa bibliothèque.
- INTERDICTION : n'utilise JAMAIS propose_add_to_library pour un jeu déjà dans la bibliothèque (y compris un jeu que tu as ajouté plus tôt dans la même conversation). Pour noter, changer le statut ou écrire un avis sur un jeu déjà présent, utilise propose_set_rating ou propose_change_status.
- propose_set_rating, propose_change_status et propose_remove_from_library acceptent SOIT user_game_id SOIT game_id. Tu DOIS en fournir un des deux.
- Dans l'historique tu reverras tes propres appels propose_* et leur retour, avec un champ "state" valant "pending", "confirmed" ou "cancelled". Si tu vois un retour confirmé pour add_to_library, le user_game_id pour ce jeu y figure (champ result_user_game_id ou user_game_id).
- Si tu n'as ni user_game_id ni game_id pour un jeu déjà dans la bibliothèque, appelle get_my_library AVANT tout propose_*.
- Ne mentionne JAMAIS un UUID, un id, un game_id ni un user_game_id à l'utilisateur dans ta réponse. Ces identifiants sont strictement internes au système."""


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


@agent.tool
async def search_games(ctx: RunContext[AgentDeps], query: str, top_k: int = 8) -> list[dict]:
    """Recherche des jeux pertinents par similarité sémantique."""
    return await retrieve_games(ctx.deps.db, query, top_k)


@agent.tool
async def search_games_multi(ctx: RunContext[AgentDeps], queries: list[str], top_k: int = 8) -> list[dict]:
    """Lance plusieurs recherches en parallèle avec des formulations différentes et déduplique les résultats."""
    batches: list[list[dict]] = list(await asyncio.gather(*[retrieve_games(ctx.deps.db, q, top_k) for q in queries]))
    seen_ids: set[str] = set()
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
            "user_game_id": str(ug.id),
            "title": game.title,
            "genres": [g.name for g in game.genres],
            "hours_played": ug.hours_played,
            "status": ug.status.value if ug.status else None,
            "user_rating": ug.user_rating,
        }
        for ug, game in rows
    ]


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
    game_id : provient d'un résultat search_games. status : "todo", "not_started", "completed", "dropped".
    rating : entier 1-10 (optionnel). review : texte libre (optionnel).
    Retourne une erreur si le jeu est déjà dans la bibliothèque."""
    try:
        gid = uuid.UUID(game_id)
    except ValueError:
        return {"error": "invalid_game_id"}

    game = await ctx.deps.db.get(Game, gid)
    if not game:
        return {"error": "game_not_found"}

    existing = await ctx.deps.db.execute(
        select(UserGame).where(UserGame.user_id == ctx.deps.user.id, UserGame.game_id == gid)
    )
    ug = existing.scalar_one_or_none()
    if ug:
        return {
            "error": "already_in_library",
            "user_game_id": str(ug.id),
            "current_status": ug.status.value if ug.status else None,
            "current_rating": ug.user_rating,
        }

    try:
        validated_status = UserGameStatus(status) if status else None
    except ValueError:
        validated_status = None

    if rating is not None and not (1 <= rating <= 10):
        return {"error": "invalid_rating", "message": "La note doit être entre 1 et 10."}

    proposal_id = str(uuid.uuid4())
    return {
        "proposal_id": proposal_id,
        "action_type": "add_to_library",
        "game_id": game_id,
        "status": validated_status.value if validated_status else None,
        "rating": rating,
        "review": review,
        "title": game.title,
        "cover_url": game.cover_url,
        "current": None,
        "target": {
            "status": validated_status.value if validated_status else None,
            "rating": rating,
            "review": review,
        },
    }


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
    game_id : l'id du jeu dans le catalogue (ex: depuis search_games ou annotation d'historique).
    new_status : "todo", "not_started", "completed", "dropped"."""
    try:
        target_status = UserGameStatus(new_status)
    except ValueError:
        return {"error": "invalid_status", "valid_values": [s.value for s in UserGameStatus]}

    ug = None
    if user_game_id:
        try:
            ugid = uuid.UUID(user_game_id)
        except ValueError:
            return {"error": "invalid_user_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.id == ugid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    elif game_id:
        try:
            gid = uuid.UUID(game_id)
        except ValueError:
            return {"error": "invalid_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.game_id == gid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    else:
        return {"error": "must_provide_user_game_id_or_game_id"}

    if not ug:
        return {"error": "not_in_library"}

    proposal_id = str(uuid.uuid4())
    return {
        "proposal_id": proposal_id,
        "action_type": "change_status",
        "user_game_id": str(ug.id),
        "new_status": target_status.value,
        "game_id": str(ug.game_id),
        "title": ug.game.title,
        "cover_url": ug.game.cover_url,
        "current": {"status": ug.status.value if ug.status else None},
        "target": {"status": target_status.value},
    }


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
    game_id : l'id du jeu dans le catalogue (ex: depuis search_games ou annotation d'historique).
    rating : entier 1-10. review : texte libre."""
    if rating is not None and not (1 <= rating <= 10):
        return {"error": "invalid_rating", "message": "La note doit être entre 1 et 10."}

    ug = None
    if user_game_id:
        try:
            ugid = uuid.UUID(user_game_id)
        except ValueError:
            return {"error": "invalid_user_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.id == ugid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    elif game_id:
        try:
            gid = uuid.UUID(game_id)
        except ValueError:
            return {"error": "invalid_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.game_id == gid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    else:
        return {"error": "must_provide_user_game_id_or_game_id"}

    if not ug:
        return {"error": "not_in_library"}

    proposal_id = str(uuid.uuid4())
    return {
        "proposal_id": proposal_id,
        "action_type": "set_rating",
        "user_game_id": str(ug.id),
        "rating": rating,
        "review": review,
        "game_id": str(ug.game_id),
        "title": ug.game.title,
        "cover_url": ug.game.cover_url,
        "current": {"rating": ug.user_rating, "review": ug.review},
        "target": {"rating": rating, "review": review},
    }


@agent.tool
async def propose_remove_from_library(
    ctx: RunContext[AgentDeps],
    user_game_id: str | None = None,
    game_id: str | None = None,
) -> dict:
    """Propose de supprimer un jeu de la bibliothèque. Ne modifie PAS la DB.
    Fournir SOIT user_game_id SOIT game_id (mais pas les deux).
    user_game_id : l'id du UserGame (obtenu via get_my_library).
    game_id : l'id du jeu dans le catalogue (ex: depuis search_games ou annotation d'historique)."""
    ug = None
    if user_game_id:
        try:
            ugid = uuid.UUID(user_game_id)
        except ValueError:
            return {"error": "invalid_user_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.id == ugid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    elif game_id:
        try:
            gid = uuid.UUID(game_id)
        except ValueError:
            return {"error": "invalid_game_id"}
        result = await ctx.deps.db.execute(
            select(UserGame).options(selectinload(UserGame.game))
            .where(UserGame.game_id == gid, UserGame.user_id == ctx.deps.user.id)
        )
        ug = result.scalar_one_or_none()
    else:
        return {"error": "must_provide_user_game_id_or_game_id"}

    if not ug:
        return {"error": "not_in_library"}

    proposal_id = str(uuid.uuid4())
    return {
        "proposal_id": proposal_id,
        "action_type": "remove_from_library",
        "user_game_id": str(ug.id),
        "game_id": str(ug.game_id),
        "title": ug.game.title,
        "cover_url": ug.game.cover_url,
        "current": {"status": ug.status.value if ug.status else None},
        "target": None,
    }


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

Fraîcheur des recommandations — la règle dépend du type de jeu :
- Jeux solo / narratifs / aventure / RPG mono-joueur : l'âge n'est pas un critère d'exclusion. Un bon jeu solo reste recommandable à tout âge. Privilégie la qualité (scores, avis Steam).
- Jeux multijoueurs / compétitifs / coop en ligne / live service : ne recommande que si la communauté est toujours active aujourd'hui. Pour un multi de plus de 5 ans, justifie explicitement la viabilité ("toujours actif en 2026"). Évite les multi dont la communauté est morte.
- Toujours indiquer l'année de sortie entre parenthèses après le titre : **Armored Core VI** (2023).

Signaux de qualité disponibles dans les résultats des outils :
- steam_score (0-100) : pourcentage d'avis positifs des joueurs sur Steam. Signal fort de satisfaction joueur — pondère tes recommandations dessus quand il est disponible.
- steam_total_reviews : volume d'avis. Un steam_score de 95 sur 200 avis est moins fiable qu'un 88 sur 50 000 avis. Ignore le score si steam_total_reviews est inférieur à 500.
- steam_reviews_summary : résumé qualitatif des avis joueurs ; cite-le quand pertinent pour justifier une recommandation.
- metacritic_score, opencritic_score, igdb_rating : scores critiques. À combiner avec le retour joueur Steam.
- Tout score affiché doit être préfixé par sa source : "Steam 83 %", "Metacritic 96 %", "OpenCritic 88 %", "IGDB 87 %". Ne jamais afficher un pourcentage nu sans source.
Quand ces signaux divergent (ex : Metacritic élevé mais Steam mitigé), mentionne-le honnêtement.

Formatage de tes réponses (markdown rendu dans l'interface) :
- Quand tu présentes plusieurs jeux, utilise une liste à puces : **Titre** (année) suivi d'une courte description.
- Utilise **gras** pour les titres de jeux et les points clés.
- Écris des paragraphes courts, jamais un seul bloc de texte.
- N'utilise pas de titres markdown (#, ##) — les listes et le gras suffisent.
- Aucun emoji, jamais.
- Pas de tableaux markdown.
- Ne crée pas de catégories thématiques inventées. Si tu groupes des jeux, utilise uniquement les genres qui apparaissent dans les résultats search_games. Si les genres ne permettent pas un regroupement naturel, présente une liste plate."""

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
