import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.taxonomy import games_genres, games_modes, games_platforms, games_steam_tags, games_tags


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        Index("idx_games_title", "title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # IGDB
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    storyline: Mapped[str | None] = mapped_column(Text)
    developer: Mapped[str | None] = mapped_column(String)
    cover_url: Mapped[str | None] = mapped_column(String)
    igdb_rating: Mapped[float | None] = mapped_column()
    igdb_rating_count: Mapped[int | None] = mapped_column(Integer)
    release_date: Mapped[datetime | None] = mapped_column(DateTime)
    igdb_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # RAWG
    metacritic_score: Mapped[int | None] = mapped_column(SmallInteger)

    # Steam
    steam_description: Mapped[str | None] = mapped_column(Text)
    steam_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    steam_score: Mapped[int | None] = mapped_column(SmallInteger)
    steam_total_reviews: Mapped[int | None] = mapped_column(Integer)
    steam_owners_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steam_owners_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steam_players_2weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steam_ccu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steam_metrics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # HLTB (heures)
    hltb_main: Mapped[float | None] = mapped_column()
    hltb_extra: Mapped[float | None] = mapped_column()
    hltb_completionist: Mapped[float | None] = mapped_column()

    # OpenCritic — JSONB consolidé (ADR-0018). Lecture via @property
    # opencritic_score / opencritic_excerpts pour compat Pydantic from_attributes.
    opencritic_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # URLs stores (steam, epic, gog, xbox, playstation, nintendo)
    store_urls: Mapped[dict[str, str] | None] = mapped_column(JSONB, nullable=True)

    # IDs sources externes
    igdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    rawg_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    steam_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    hltb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    opencritic_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    psn_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    xbox_id: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)

    ingestion_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    # Facades de compat : Pydantic schemas (from_attributes=True) lisent
    # encore .opencritic_score et .opencritic_excerpts ; le frontend consomme
    # ces deux champs flats. La colonne sous-jacente est désormais JSONB.
    @property
    def opencritic_score(self) -> int | None:
        return (self.opencritic_signals or {}).get("score")

    @property
    def opencritic_excerpts(self) -> list[str] | None:
        return (self.opencritic_signals or {}).get("excerpts")

    # Relationships
    genres: Mapped[list["Genre"]] = relationship(secondary=games_genres, back_populates="games")
    platforms: Mapped[list["Platform"]] = relationship(secondary=games_platforms, back_populates="games")
    modes: Mapped[list["GameMode"]] = relationship(secondary=games_modes, back_populates="games")
    tags: Mapped[list["Tag"]] = relationship(secondary=games_tags, back_populates="games")
    steam_tags: Mapped[list["SteamTag"]] = relationship(secondary=games_steam_tags, back_populates="games")
    embeddings: Mapped[list["GameEmbedding"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    user_games: Mapped[list["UserGame"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class GameEmbedding(Base):
    __tablename__ = "game_embeddings"
    __table_args__ = (
        UniqueConstraint("game_id", "model_version", name="uq_game_embeddings_game_model"),
        Index("idx_game_embeddings_game_id", "game_id"),
        # Index HNSW à ajouter manuellement dans la migration Alembic :
        # op.execute("CREATE INDEX idx_game_embeddings_hnsw ON game_embeddings USING hnsw (embedding vector_cosine_ops)")
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="BAAI/bge-m3")
    embedding: Mapped[Any] = mapped_column(Vector(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    game: Mapped["Game"] = relationship(back_populates="embeddings")
