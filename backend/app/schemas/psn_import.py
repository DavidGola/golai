import uuid

from pydantic import BaseModel, Field

from app.models.user_game import UserGameStatus


class PSNPreviewRequest(BaseModel):
    online_id: str = Field(..., pattern=r"^[\w-]{3,16}$")


class PSNPreviewItem(BaseModel):
    game_id: uuid.UUID
    title: str
    cover_url: str | None
    trophy_progress_pct: int | None
    hours_played: float | None
    suggested_status: UserGameStatus | None
    already_in_library: bool


class PSNPreviewResponse(BaseModel):
    items: list[PSNPreviewItem]


class PSNConfirmItem(BaseModel):
    game_id: uuid.UUID
    status: UserGameStatus | None = None
    user_rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None
    hours_played: float | None = None


class PSNConfirmRequest(BaseModel):
    items: list[PSNConfirmItem]


class PSNConfirmResponse(BaseModel):
    imported: int
    skipped: int
