import uuid

from pydantic import BaseModel, Field

from app.models.user_game import UserGameStatus


class SteamPreviewRequest(BaseModel):
    profile: str


class SteamPreviewItem(BaseModel):
    game_id: uuid.UUID
    title: str
    cover_url: str | None
    hours_on_record: float | None
    suggested_status: UserGameStatus | None
    already_in_library: bool


class SteamPreviewResponse(BaseModel):
    items: list[SteamPreviewItem]
    resolved_steam_id: str


class SteamConfirmItem(BaseModel):
    game_id: uuid.UUID
    status: UserGameStatus | None = None
    user_rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None
    hours_on_record: float | None = None


class SteamConfirmRequest(BaseModel):
    items: list[SteamConfirmItem]
    steam_id: str


class SteamConfirmResponse(BaseModel):
    imported: int
    skipped: int
