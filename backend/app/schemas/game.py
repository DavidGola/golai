import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.taxonomy import GameModeRead, GenreRead, PlatformRead, TagRead


class GameListItem(BaseModel):
    id: uuid.UUID
    title: str
    cover_url: str | None = None
    release_date: datetime | None = None
    igdb_rating: float | None = None
    metacritic_score: int | None = None
    opencritic_score: int | None = None
    steam_score: int | None = None
    steam_id: int | None = None
    hltb_main: float | None = None
    edition_type: Literal["original", "remaster", "remake", "expanded"] = "original"
    parent_game_id: uuid.UUID | None = None
    genres: list[GenreRead] = []
    platforms: list[PlatformRead] = []

    model_config = ConfigDict(from_attributes=True)


class GameRead(GameListItem):
    summary: str | None = None
    storyline: str | None = None
    developer: str | None = None
    steam_description: str | None = None
    steam_reviews_summary: str | None = None
    hltb_extra: float | None = None
    hltb_completionist: float | None = None
    opencritic_excerpts: list[str] | None = None
    keywords: list[str] | None = None
    modes: list[GameModeRead] = []
    tags: list[TagRead] = []


class GameListResponse(BaseModel):
    items: list[GameListItem]
    total: int
    page: int
    page_size: int
