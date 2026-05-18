import uuid

from pydantic import BaseModel, Field

from app.models.user_game import UserGameStatus


class XboxPreviewRequest(BaseModel):
    gamertag: str = Field(..., min_length=1, max_length=15, pattern=r"^[\w\s]+$")


class XboxPreviewItem(BaseModel):
    game_id: uuid.UUID
    title: str
    cover_url: str | None
    achievement_progress_pct: int | None
    suggested_status: UserGameStatus | None
    already_in_library: bool


class XboxPreviewResponse(BaseModel):
    items: list[XboxPreviewItem]


class XboxConfirmItem(BaseModel):
    game_id: uuid.UUID
    status: UserGameStatus | None = None
    user_rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None


class XboxConfirmRequest(BaseModel):
    items: list[XboxConfirmItem]
    gamertag: str = Field(..., min_length=1, max_length=15, pattern=r"^[\w\s]+$")


class XboxConfirmResponse(BaseModel):
    imported: int
    skipped: int
