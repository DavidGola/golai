import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class UserGameStatus(str, enum.Enum):
    completed = "completed"
    todo = "todo"
    dropped = "dropped"
    not_started = "not_started"


class UserGame(Base):
    __tablename__ = "user_games"
    __table_args__ = (
        UniqueConstraint("user_id", "game_id", name="uq_user_games_user_game"),
        CheckConstraint("user_rating BETWEEN 1 AND 10", name="ck_user_games_rating"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[UserGameStatus | None] = mapped_column(SAEnum(UserGameStatus, name="user_game_status", create_type=False))
    user_rating: Mapped[int | None] = mapped_column(SmallInteger)
    review: Mapped[str | None] = mapped_column(Text)
    hours_played: Mapped[float | None] = mapped_column()
    source: Mapped[str | None] = mapped_column(String(16))
    added_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()

    user: Mapped["User"] = relationship(back_populates="user_games")
    game: Mapped["Game"] = relationship(back_populates="user_games")
