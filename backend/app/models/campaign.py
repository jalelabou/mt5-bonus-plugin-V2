import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Float, Boolean, Enum, DateTime, ForeignKey, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    ARCHIVED = "archived"


class BonusType(str, enum.Enum):
    TYPE_A = "A"  # Dynamic Leverage
    TYPE_B = "B"  # Fixed Leverage
    TYPE_C = "C"  # Convertible


class LotTrackingScope(str, enum.Enum):
    ALL = "all"
    POST_BONUS = "post_bonus"
    SYMBOL_FILTERED = "symbol_filtered"
    PER_TRADE_THRESHOLD = "per_trade_threshold"


class TriggerType(str, enum.Enum):
    AUTO_DEPOSIT = "auto_deposit"
    PROMO_CODE = "promo_code"
    REGISTRATION = "registration"
    AGENT_CODE = "agent_code"


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT, index=True
    )
    bonus_type: Mapped[BonusType] = mapped_column(Enum(BonusType))
    bonus_percentage: Mapped[float] = mapped_column(Float)
    max_bonus_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_deposit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_deposit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Type C specific
    lot_requirement: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lot_tracking_scope: Mapped[Optional[LotTrackingScope]] = mapped_column(
        Enum(LotTrackingScope), nullable=True
    )
    symbol_filter: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    per_trade_lot_minimum: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Dates
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Targeting
    target_mt5_groups: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    target_countries: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Triggers
    trigger_types: Mapped[list] = mapped_column(JSON, default=list)
    promo_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    agent_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Limits
    one_bonus_per_account: Mapped[bool] = mapped_column(Boolean, default=False)
    max_concurrent_bonuses: Mapped[int] = mapped_column(Integer, default=1)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Multi-tenancy
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)

    # Relations
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("admin_users.id"), nullable=True
    )
    created_by = relationship("AdminUser", foreign_keys=[created_by_id])
    broker = relationship("Broker", foreign_keys=[broker_id])
    bonuses = relationship("Bonus", back_populates="campaign")
