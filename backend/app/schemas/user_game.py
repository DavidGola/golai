import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_game import UserGameStatus
from app.schemas.game import GameListItem


class UserGameCreate(BaseModel):
    game_id: uuid.UUID
    status: UserGameStatus | None = None
    user_rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None
    hours_played: float | None = None


class UserGameUpdate(BaseModel):
    status: UserGameStatus | None = None
    user_rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None
    hours_played: float | None = None


class UserGameRead(BaseModel):
    id: uuid.UUID
    game_id: uuid.UUID
    status: UserGameStatus | None = None
    user_rating: int | None = None
    review: str | None = None
    hours_played: float | None = None
    added_at: datetime
    completed_at: datetime | None = None
    game: GameListItem

    model_config = ConfigDict(from_attributes=True)
