from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.gateway.registry import gateway_registry
from app.models.audit_log import AuditLog
from app.models.bonus import Bonus
from app.models.campaign import Campaign
from app.models.user import AdminUser
from app.schemas.audit_log import AuditLogRead
from app.schemas.bonus import BonusRead

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/mt5-metadata")
async def mt5_metadata(
    user: AdminUser = Depends(get_current_user),
):
    """Return all MT5 groups, countries, and accounts for form dropdowns."""
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")

    gw = gateway_registry.get_gateway(broker_id)
    if not gw:
        raise HTTPException(status_code=503, detail="MT5 gateway not available for this broker")

    all_groups = await gw.get_all_groups()

    all_logins = await gw.get_all_logins()
    countries = set()
    accounts = []
    for login in all_logins:
        acct = await gw.get_account_info(str(login))
        if acct:
            countries.add(acct.country)
            accounts.append({
                "login": acct.login,
                "name": acct.name,
                "group": acct.group,
                "country": acct.country,
            })
    return {
        "groups": sorted(set(all_groups)),
        "countries": sorted(countries),
        "accounts": accounts,
    }


@router.get("/{login}")
async def account_lookup(
    login: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")

    gw = gateway_registry.get_gateway(broker_id)
    if not gw:
        raise HTTPException(status_code=503, detail="MT5 gateway not available")

    account = await gw.get_account_info(login)
    if not account:
        raise HTTPException(status_code=404, detail="MT5 account not found")

    # Get bonuses (scoped to broker)
    result = await db.execute(
        select(Bonus, Campaign.name)
        .join(Campaign, Bonus.campaign_id == Campaign.id)
        .where(Bonus.mt5_login == login, Bonus.broker_id == broker_id)
        .order_by(Bonus.assigned_at.desc())
    )
    bonus_rows = result.all()
    bonuses = []
    for bonus, campaign_name in bonus_rows:
        item = BonusRead.model_validate(bonus)
        item.campaign_name = campaign_name
        if bonus.bonus_type == "C" and bonus.lots_required:
            item.percent_converted = round(bonus.lots_traded / bonus.lots_required * 100, 2)
        bonuses.append(item)

    # Get audit logs (scoped to broker)
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.mt5_login == login, AuditLog.broker_id == broker_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    audit_logs = [AuditLogRead.model_validate(a) for a in audit_result.scalars().all()]

    return {
        "account": {
            "login": account.login,
            "name": account.name,
            "balance": account.balance,
            "equity": account.equity,
            "credit": account.credit,
            "leverage": account.leverage,
            "group": account.group,
            "country": account.country,
        },
        "bonuses": bonuses,
        "audit_logs": audit_logs,
    }
