import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.taxonomy import user_favorite_genres, user_important_criteria

import enum


class PlaytimePreference(str, enum.Enum):
    short = "short"
    medium = "medium"
    long = "long"


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(nullable=False, unique=True)
    preferred_playtime: Mapped[PlaytimePreference | None] = mapped_column(
        SAEnum(PlaytimePreference, name="playtime_preference")
    )
    steam_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    preferred_platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_steam_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    psn_online_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    last_psn_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    xbox_gamertag: Mapped[str | None] = mapped_column(String(15), unique=True)
    last_xbox_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_games: Mapped[list["UserGame"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favorite_genres: Mapped[list["Genre"]] = relationship(secondary=user_favorite_genres, back_populates="favorited_by")
    important_criteria: Mapped[list["Criterion"]] = relationship(secondary=user_important_criteria, back_populates="considered_by")
