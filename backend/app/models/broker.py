import secrets
from typing import Optional

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def _generate_api_key() -> str:
    return secrets.token_hex(32)


class Broker(TimestampMixin, Base):
    __tablename__ = "brokers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # MT5 connection credentials
    mt5_bridge_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mt5_server: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mt5_manager_login: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mt5_manager_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # API key for external trigger authentication
    api_key: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True, default=_generate_api_key
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def mt5_configured(self) -> bool:
        return all([self.mt5_bridge_url, self.mt5_server, self.mt5_manager_login, self.mt5_manager_password])
