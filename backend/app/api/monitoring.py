from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.database import get_db
from app.gateway.registry import gateway_registry
from app.models.monitored_account import MonitoredAccount
from app.models.user import AdminRole, AdminUser
from app.services.monitor_service import register_for_monitoring

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/accounts")
async def list_monitored_accounts(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = select(MonitoredAccount)
    if broker_id:
        query = query.where(MonitoredAccount.broker_id == broker_id)
    if active_only:
        query = query.where(MonitoredAccount.is_active == True)  # noqa: E712
    query = query.order_by(MonitoredAccount.last_polled_at.desc())
    result = await db.execute(query)
    accounts = result.scalars().all()
    return {"accounts": [_serialize(a) for a in accounts]}


@router.post("/accounts/{mt5_login}/register")
async def register_account(
    mt5_login: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN, AdminRole.CAMPAIGN_MANAGER)),
):
    """Manually register an account for deposit monitoring."""
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")
    mon = await register_for_monitoring(db, mt5_login, reason="deposit_watch", broker_id=broker_id)
    await db.commit()
    return _serialize(mon)


@router.post("/accounts/{mt5_login}/reset-errors")
async def reset_errors(
    mt5_login: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN)),
):
    """Reset consecutive error counter for a stuck account."""
    broker_id = user.broker_id
    query = select(MonitoredAccount).where(MonitoredAccount.mt5_login == mt5_login)
    if broker_id:
        query = query.where(MonitoredAccount.broker_id == broker_id)
    result = await db.execute(query)
    mon = result.scalar_one_or_none()
    if not mon:
        raise HTTPException(404, "Account not monitored")
    mon.consecutive_errors = 0
    mon.last_error = None
    mon.is_active = True
    await db.commit()
    return _serialize(mon)


@router.get("/status")
async def monitoring_status(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    from app.tasks.scheduler import scheduler

    broker_id = user.broker_id
    base_q = select(func.count(MonitoredAccount.id))
    if broker_id:
        base_q = base_q.where(MonitoredAccount.broker_id == broker_id)

    total = (await db.execute(base_q)).scalar() or 0
    active = (await db.execute(
        base_q.where(MonitoredAccount.is_active == True)  # noqa: E712
    )).scalar() or 0
    errored = (await db.execute(
        base_q.where(MonitoredAccount.consecutive_errors >= 5)
    )).scalar() or 0

    monitor_job = scheduler.get_job("account_monitor")
    return {
        "total_accounts": total,
        "active_accounts": active,
        "errored_accounts": errored,
        "scheduler_running": scheduler.running,
        "next_run": str(monitor_job.next_run_time) if monitor_job else None,
    }


@router.post("/accounts/{mt5_login}/test-deposit")
async def test_deposit(
    mt5_login: str,
    amount: float = 500.0,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN)),
):
    """Deposit to MT5 balance (for testing auto-detection)."""
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")
    gw = gateway_registry.get_gateway(broker_id)
    if not gw:
        raise HTTPException(status_code=503, detail="MT5 gateway not available")

    ok = await gw.deposit_to_balance(mt5_login, amount, f"Test deposit {amount}")
    if not ok:
        raise HTTPException(500, "Deposit failed")
    acct = await gw.get_account_info(mt5_login)
    return {
        "success": True,
        "amount": amount,
        "new_balance": acct.balance if acct else None,
        "new_equity": acct.equity if acct else None,
        "new_credit": acct.credit if acct else None,
    }


@router.post("/accounts/{mt5_login}/test-withdraw")
async def test_withdraw(
    mt5_login: str,
    amount: float = 500.0,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN)),
):
    """Withdraw from MT5 balance (for testing auto-detection)."""
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")
    gw = gateway_registry.get_gateway(broker_id)
    if not gw:
        raise HTTPException(status_code=503, detail="MT5 gateway not available")

    ok = await gw.deposit_to_balance(mt5_login, -abs(amount), f"Test withdrawal {amount}")
    if not ok:
        raise HTTPException(500, "Withdrawal failed")
    acct = await gw.get_account_info(mt5_login)
    return {
        "success": True,
        "amount": -abs(amount),
        "new_balance": acct.balance if acct else None,
        "new_equity": acct.equity if acct else None,
        "new_credit": acct.credit if acct else None,
    }


def _serialize(mon: MonitoredAccount) -> dict:
    return {
        "mt5_login": mon.mt5_login,
        "broker_id": mon.broker_id,
        "last_balance": mon.last_balance,
        "last_equity": mon.last_equity,
        "last_credit": mon.last_credit,
        "is_active": mon.is_active,
        "monitor_reasons": mon.monitor_reasons,
        "consecutive_errors": mon.consecutive_errors,
        "last_error": mon.last_error,
        "last_polled_at": str(mon.last_polled_at) if mon.last_polled_at else None,
    }
