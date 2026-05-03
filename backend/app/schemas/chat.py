from typing import Literal

from pydantic import BaseModel


class AnonymousHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AnonymousMessageCreate(BaseModel):
    content: str
    history: list[AnonymousHistoryMessage] = []


class ChatConfigRead(BaseModel):
    model: str
