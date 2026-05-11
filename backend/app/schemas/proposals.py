import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.message_proposal import ProposalActionType, ProposalState


class ProposalRead(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    action_type: ProposalActionType
    payload: dict[str, Any]
    state: ProposalState
    state_changed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
