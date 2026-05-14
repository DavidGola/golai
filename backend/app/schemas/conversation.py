import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from app.schemas.proposals import ProposalRead
from app.schemas.store import CitedGame


class ChatIntent(str, Enum):
    LIBRARY_RECOMMEND = "library_recommend"


class MessageCreate(BaseModel):
    content: str
    intent: ChatIntent | None = None


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageRead(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    tokens_used: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    cited_games: list[CitedGame] | None = None
    created_at: datetime
    proposals: list[ProposalRead] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationWithMessages(ConversationRead):
    messages: list[MessageRead] = []
