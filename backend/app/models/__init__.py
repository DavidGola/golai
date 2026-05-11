# Importer tous les modèles ici pour qu'Alembic autogenerate les détecte.

from app.models.conversation import Conversation, Message, MessageRole
from app.models.message_proposal import MessageProposal, ProposalActionType, ProposalState
from app.models.game import Game, GameEmbedding
from app.models.rate_limit import RateLimitBucket
from app.models.taxonomy import (
    Criterion,
    Genre,
    GameMode,
    Platform,
    Tag,
    games_genres,
    games_modes,
    games_platforms,
    games_tags,
    user_favorite_genres,
    user_important_criteria,
)
from app.models.user import PlaytimePreference, User
from app.models.user_game import UserGame, UserGameStatus
from app.models.sync_state import SyncState

__all__ = [
    "SyncState",
    "MessageProposal",
    "ProposalActionType",
    "ProposalState",
    "Conversation",
    "Criterion",
    "Game",
    "GameEmbedding",
    "GameMode",
    "Genre",
    "Message",
    "MessageRole",
    "Platform",
    "PlaytimePreference",
    "RateLimitBucket",
    "Tag",
    "User",
    "UserGame",
    "UserGameStatus",
    "games_genres",
    "games_modes",
    "games_platforms",
    "games_tags",
    "user_favorite_genres",
    "user_important_criteria",
]
