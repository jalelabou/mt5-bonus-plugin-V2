import enum
from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey, Index
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventType(str, enum.Enum):
    ASSIGNMENT = "assignment"
    CANCELLATION = "cancellation"
    CONVERSION_STEP = "conversion_step"
    LEVERAGE_CHANGE = "leverage_change"
    EXPIRY = "expiry"
    ADMIN_OVERRIDE = "admin_override"


class ActorType(str, enum.Enum):
    SYSTEM = "system"
    ADMIN = "admin"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brokers.id"), nullable=True, index=True
    )
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mt5_login: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True, index=True
    )
    bonus_id: Mapped[int | None] = mapped_column(ForeignKey("bonuses.id"), nullable=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType))
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
