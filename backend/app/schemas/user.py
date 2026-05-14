import uuid
from datetime import datetime
from typing import Literal

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PlaytimePreference
from app.schemas.taxonomy import CriterionRead, GenreRead

STORE_PLATFORMS = Literal["steam", "playstation", "nintendo", "xbox", "epic", "gog"]


class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str
    preferred_playtime: PlaytimePreference | None = None
    preferred_platform: STORE_PLATFORMS | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfile(UserRead):
    """UserRead enrichi avec les relations — utilisé par /users/me GET."""
    favorite_genres: list[GenreRead] = []
    important_criteria: list[CriterionRead] = []


class UserCreate(schemas.BaseUserCreate):
    username: str


class UserUpdate(schemas.BaseUserUpdate):
    username: str | None = None
    preferred_playtime: PlaytimePreference | None = None


class UserPatchMe(schemas.BaseUserUpdate):
    """Schéma pour PATCH /users/me — inclut genre/critères en plus des champs user."""
    username: str | None = None
    preferred_playtime: PlaytimePreference | None = None
    preferred_platform: STORE_PLATFORMS | None = None
    favorite_genre_ids: list[int] | None = None
    important_criterion_ids: list[int] | None = None


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1)
