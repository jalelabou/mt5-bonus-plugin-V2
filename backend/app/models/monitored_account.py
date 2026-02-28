from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MonitoredAccount(Base):
    __tablename__ = "monitored_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), index=True)
    mt5_login: Mapped[str] = mapped_column(String(50), index=True)

    # Snapshot fields (updated each poll cycle)
    last_balance: Mapped[float] = mapped_column(Float, default=0.0)
    last_equity: Mapped[float] = mapped_column(Float, default=0.0)
    last_credit: Mapped[float] = mapped_column(Float, default=0.0)

    # Deal tracking watermark for deposit detection and Type C
    last_deal_timestamp: Mapped[float] = mapped_column(Float, default=0.0)

    # Monitoring state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    monitor_reasons: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Error tracking (skip accounts with persistent failures)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("mt5_login", "broker_id", name="uq_monitored_mt5_broker"),
    )
