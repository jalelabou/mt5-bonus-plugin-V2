"""Broker-scoped user management — Broker Admin can CRUD sub-admins."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config.security import hash_password
from app.db.database import get_db
from app.models.user import AdminRole, AdminUser
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


def _require_broker_admin(user: AdminUser):
    """Verify the user is a Broker Admin (is_broker_admin=True and has a broker_id)."""
    if not user.broker_id or not user.is_broker_admin:
        raise HTTPException(status_code=403, detail="Broker admin access required")


@router.get("", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    """List all sub-admins for this broker."""
    if not user.broker_id:
        raise HTTPException(status_code=400, detail="No broker context")

    result = await db.execute(
        select(AdminUser).where(AdminUser.broker_id == user.broker_id)
    )
    return [UserRead.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    """Create a sub-admin for this broker. Only Broker Admins can do this."""
    _require_broker_admin(user)

    # Check email uniqueness
    existing = await db.execute(select(AdminUser).where(AdminUser.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")

    new_user = AdminUser(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        broker_id=user.broker_id,
        is_broker_admin=False,  # Sub-admins are never broker admins
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    return UserRead.model_validate(new_user)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    """Update a sub-admin. Broker Admin only."""
    _require_broker_admin(user)

    target = await db.get(AdminUser, user_id)
    if not target or target.broker_id != user.broker_id:
        raise HTTPException(status_code=404, detail="User not found")

    # Can't modify the broker admin itself
    if target.is_broker_admin:
        raise HTTPException(status_code=400, detail="Cannot modify the broker admin")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(target, field, value)

    await db.flush()
    await db.refresh(target)
    return UserRead.model_validate(target)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    """Deactivate a sub-admin. Broker Admin only."""
    _require_broker_admin(user)

    target = await db.get(AdminUser, user_id)
    if not target or target.broker_id != user.broker_id:
        raise HTTPException(status_code=404, detail="User not found")

    if target.is_broker_admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate the broker admin")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    target.is_active = False
    await db.flush()
    return {"status": "deactivated"}
