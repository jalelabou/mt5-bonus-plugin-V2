import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TriggerStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerEvent(Base):
    __tablename__ = "trigger_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    mt5_login: Mapped[str] = mapped_column(String(50), index=True)
    trigger_type: Mapped[str] = mapped_column(String(50))
    event_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[TriggerStatus] = mapped_column(
        Enum(TriggerStatus), default=TriggerStatus.PENDING
    )
    skip_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
