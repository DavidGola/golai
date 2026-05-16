from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ─────────────────────────────────────────
# Tables de liaison pures (M:N sans attrs)
# Définies ici pour éviter les imports circulaires.
# ─────────────────────────────────────────

games_genres = Table(
    "games_genres",
    Base.metadata,
    Column("game_id", UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True),
    Index("idx_games_genres_genre_id", "genre_id"),
)

games_platforms = Table(
    "games_platforms",
    Base.metadata,
    Column("game_id", UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("platform_id", Integer, ForeignKey("platforms.id", ondelete="RESTRICT"), primary_key=True),
    Index("idx_games_platforms_platform_id", "platform_id"),
)

games_modes = Table(
    "games_modes",
    Base.metadata,
    Column("game_id", UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("mode_id", Integer, ForeignKey("game_modes.id", ondelete="RESTRICT"), primary_key=True),
    Index("idx_games_modes_mode_id", "mode_id"),
)

games_tags = Table(
    "games_tags",
    Base.metadata,
    Column("game_id", UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
    Index("idx_games_tags_tag_id", "tag_id"),
)

games_steam_tags = Table(
    "games_steam_tags",
    Base.metadata,
    Column("game_id", UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("steam_tags.id", ondelete="CASCADE"), primary_key=True),
    Column("vote_count", Integer, nullable=True),
    Index("idx_games_steam_tags_tag_id", "tag_id"),
)

user_favorite_genres = Table(
    "user_favorite_genres",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True),
)

user_important_criteria = Table(
    "user_important_criteria",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("criterion_id", Integer, ForeignKey("criteria.id", ondelete="RESTRICT"), primary_key=True),
)


# ─────────────────────────────────────────
# Référentiels (tables statiques, seedées)
# ─────────────────────────────────────────

class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    games: Mapped[list["Game"]] = relationship(secondary=games_genres, back_populates="genres")
    favorited_by: Mapped[list["User"]] = relationship(secondary=user_favorite_genres, back_populates="favorite_genres")


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    games: Mapped[list["Game"]] = relationship(secondary=games_platforms, back_populates="platforms")


class GameMode(Base):
    __tablename__ = "game_modes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    games: Mapped[list["Game"]] = relationship(secondary=games_modes, back_populates="modes")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    games: Mapped[list["Game"]] = relationship(secondary=games_tags, back_populates="tags")


class SteamTag(Base):
    __tablename__ = "steam_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    games: Mapped[list["Game"]] = relationship(secondary=games_steam_tags, back_populates="steam_tags")


class Criterion(Base):
    __tablename__ = "criteria"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    considered_by: Mapped[list["User"]] = relationship(secondary=user_important_criteria, back_populates="important_criteria")
