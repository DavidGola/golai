from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    source: Mapped[str] = mapped_column(String, primary_key=True)
    last_sync: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
