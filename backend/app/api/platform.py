"""Platform admin API — manage brokers and their initial admin users."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.config.security import hash_password
from app.db.database import get_db
from app.gateway.registry import gateway_registry
from app.models.broker import Broker
from app.models.user import AdminRole, AdminUser
from app.schemas.broker import BrokerAdminCreate, BrokerCreate, BrokerRead, BrokerUpdate
from app.schemas.user import UserRead

router = APIRouter(prefix="/api/platform", tags=["platform"])


@router.get("/brokers", response_model=list[BrokerRead])
async def list_brokers(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    result = await db.execute(select(Broker).order_by(Broker.created_at.desc()))
    brokers = result.scalars().all()
    return [BrokerRead.model_validate(b) for b in brokers]


@router.post("/brokers", response_model=BrokerRead, status_code=201)
async def create_broker(
    body: BrokerCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    # Check slug uniqueness
    existing = await db.execute(select(Broker).where(Broker.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already in use")

    broker = Broker(**body.model_dump())
    db.add(broker)
    await db.flush()
    await db.refresh(broker)

    # Register gateway if MT5 is configured
    if broker.mt5_configured:
        try:
            await gateway_registry.register_broker(
                broker_id=broker.id,
                bridge_url=broker.mt5_bridge_url,
                mt5_server=broker.mt5_server,
                manager_login=broker.mt5_manager_login,
                manager_password=broker.mt5_manager_password,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"MT5 connection failed: {e}")

    return BrokerRead.model_validate(broker)


@router.get("/brokers/{broker_id}", response_model=BrokerRead)
async def get_broker(
    broker_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    broker = await db.get(Broker, broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return BrokerRead.model_validate(broker)


@router.put("/brokers/{broker_id}", response_model=BrokerRead)
async def update_broker(
    broker_id: int,
    body: BrokerUpdate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    broker = await db.get(Broker, broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    # Track if MT5 creds changed
    mt5_fields = {"mt5_bridge_url", "mt5_server", "mt5_manager_login", "mt5_manager_password"}
    update_data = body.model_dump(exclude_unset=True)
    mt5_changed = any(f in update_data for f in mt5_fields)

    for field, value in update_data.items():
        setattr(broker, field, value)
    await db.flush()
    await db.refresh(broker)

    # Refresh gateway if MT5 creds changed
    if mt5_changed and broker.mt5_configured:
        try:
            await gateway_registry.refresh_broker(
                broker_id=broker.id,
                bridge_url=broker.mt5_bridge_url,
                mt5_server=broker.mt5_server,
                manager_login=broker.mt5_manager_login,
                manager_password=broker.mt5_manager_password,
            )
        except Exception:
            pass  # Gateway reconnect failed, but broker data is updated

    return BrokerRead.model_validate(broker)


@router.patch("/brokers/{broker_id}/status", response_model=BrokerRead)
async def toggle_broker_status(
    broker_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    broker = await db.get(Broker, broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker.is_active = not broker.is_active
    await db.flush()

    if not broker.is_active:
        await gateway_registry.unregister_broker(broker_id)
    elif broker.mt5_configured:
        try:
            await gateway_registry.register_broker(
                broker_id=broker.id,
                bridge_url=broker.mt5_bridge_url,
                mt5_server=broker.mt5_server,
                manager_login=broker.mt5_manager_login,
                manager_password=broker.mt5_manager_password,
            )
        except Exception:
            pass

    return BrokerRead.model_validate(broker)


@router.post("/brokers/{broker_id}/admin", response_model=UserRead, status_code=201)
async def create_broker_admin(
    broker_id: int,
    body: BrokerAdminCreate,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    """Create the initial Broker Admin for a broker."""
    broker = await db.get(Broker, broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    # Check if broker already has an admin
    existing = await db.execute(
        select(AdminUser).where(
            AdminUser.broker_id == broker_id,
            AdminUser.is_broker_admin == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Broker already has an admin")

    # Check email uniqueness
    email_check = await db.execute(select(AdminUser).where(AdminUser.email == body.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already in use")

    admin = AdminUser(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=AdminRole.SUPER_ADMIN,
        broker_id=broker_id,
        is_broker_admin=True,
    )
    db.add(admin)
    await db.flush()
    await db.refresh(admin)
    return UserRead.model_validate(admin)


@router.get("/brokers/{broker_id}/admins", response_model=list[UserRead])
async def list_broker_admins(
    broker_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_platform_admin),
):
    broker = await db.get(Broker, broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    result = await db.execute(
        select(AdminUser).where(AdminUser.broker_id == broker_id)
    )
    return [UserRead.model_validate(u) for u in result.scalars().all()]
