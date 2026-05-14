import uuid
from typing import Literal

from pydantic import BaseModel


STORE_PLATFORMS = Literal["steam", "playstation", "nintendo", "xbox", "epic", "gog"]


class StoreLink(BaseModel):
    platform: STORE_PLATFORMS
    url: str


class CitedGame(BaseModel):
    id: uuid.UUID
    title: str
    cover_url: str | None = None
    store_links: list[StoreLink] = []
    platforms: list[str] = []
