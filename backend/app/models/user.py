import enum
from typing import Optional

from sqlalchemy import String, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    CAMPAIGN_MANAGER = "campaign_manager"
    SUPPORT_AGENT = "support_agent"
    READ_ONLY = "read_only"


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole), default=AdminRole.READ_ONLY)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Multi-tenancy: NULL = platform super admin, set = broker user
    broker_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brokers.id"), nullable=True, index=True
    )
    is_broker_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    broker = relationship("Broker", foreign_keys=[broker_id])

    @property
    def is_platform_admin(self) -> bool:
        return self.broker_id is None and self.role == AdminRole.SUPER_ADMIN
