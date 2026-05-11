import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Message


class ProposalActionType(str, enum.Enum):
    add_to_library = "add_to_library"
    change_status = "change_status"
    set_rating = "set_rating"
    remove_from_library = "remove_from_library"


class ProposalState(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class MessageProposal(Base):
    __tablename__ = "message_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[ProposalActionType] = mapped_column(
        SAEnum(ProposalActionType, name="proposal_action_type"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state: Mapped[ProposalState] = mapped_column(
        SAEnum(ProposalState, name="proposal_state"),
        nullable=False,
        default=ProposalState.pending,
        server_default="pending",
    )
    state_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="proposals")
