from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import decode_token
from app.db.database import get_db
from app.models.broker import Broker
from app.models.user import AdminRole, AdminUser

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(AdminUser).where(AdminUser.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_roles(*roles: AdminRole):
    async def role_checker(user: AdminUser = Depends(get_current_user)) -> AdminUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role.value} not authorized",
            )
        return user

    return role_checker


async def require_platform_admin(
    user: AdminUser = Depends(get_current_user),
) -> AdminUser:
    """Require the user to be a platform super admin (broker_id is NULL)."""
    if not user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return user


async def get_current_broker(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[Broker]:
    """Resolve broker from subdomain slug set by BrokerContextMiddleware."""
    slug = getattr(request.state, "broker_slug", None)
    if not slug:
        return None
    result = await db.execute(select(Broker).where(Broker.slug == slug))
    return result.scalar_one_or_none()


async def require_broker(
    broker: Optional[Broker] = Depends(get_current_broker),
) -> Broker:
    """Require a valid broker context. Fails if no broker subdomain or broker not found."""
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No broker context. Use a broker subdomain.",
        )
    if not broker.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Broker is deactivated",
        )
    return broker
