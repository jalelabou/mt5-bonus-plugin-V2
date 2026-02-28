import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Enum, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class BonusStatus(str, enum.Enum):
    ACTIVE = "active"
    CONVERTED = "converted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Bonus(TimestampMixin, Base):
    __tablename__ = "bonuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    mt5_login: Mapped[str] = mapped_column(String(50), index=True)
    bonus_type: Mapped[str] = mapped_column(String(1))  # A, B, or C
    bonus_amount: Mapped[float] = mapped_column(Float)

    # Type A leverage tracking
    original_leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    adjusted_leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Type C lot tracking
    lots_required: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lots_traded: Mapped[float] = mapped_column(Float, default=0.0)
    amount_converted: Mapped[float] = mapped_column(Float, default=0.0)

    # Status
    status: Mapped[BonusStatus] = mapped_column(
        Enum(BonusStatus), default=BonusStatus.ACTIVE, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relations
    campaign = relationship("Campaign", back_populates="bonuses")
    lot_progress = relationship("BonusLotProgress", back_populates="bonus")

    __table_args__ = (
        Index("ix_bonuses_mt5_status", "mt5_login", "status"),
        Index("ix_bonuses_campaign_status", "campaign_id", "status"),
    )


class BonusLotProgress(Base):
    __tablename__ = "bonus_lot_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)
    bonus_id: Mapped[int] = mapped_column(ForeignKey("bonuses.id"), index=True)
    deal_id: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(50))
    lots: Mapped[float] = mapped_column(Float)
    amount_converted: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(__import__("datetime").timezone.utc),
    )

    bonus = relationship("Bonus", back_populates="lot_progress")
