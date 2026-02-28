from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.database import get_db
from app.gateway.registry import gateway_registry
from app.models.bonus import Bonus, BonusLotProgress, BonusStatus
from app.models.campaign import Campaign
from app.models.user import AdminRole, AdminUser
from app.schemas.bonus import (
    BonusAssign,
    BonusCancelRequest,
    BonusDetailRead,
    BonusOverrideLeverage,
    BonusRead,
    LotProgressRead,
)
from app.schemas.common import PaginatedResponse
from app.services.bonus_engine import assign_bonus, cancel_bonus, check_eligibility
from app.services.lot_tracker import process_deal

router = APIRouter(prefix="/api/bonuses", tags=["bonuses"])


@router.get("", response_model=PaginatedResponse[BonusRead])
async def list_bonuses(
    campaign_id: Optional[int] = None,
    mt5_login: Optional[str] = None,
    bonus_type: Optional[str] = None,
    status_filter: Optional[BonusStatus] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = select(Bonus, Campaign.name).join(Campaign, Bonus.campaign_id == Campaign.id)
    count_query = select(func.count(Bonus.id))

    # Scope to broker
    if broker_id:
        query = query.where(Bonus.broker_id == broker_id)
        count_query = count_query.where(Bonus.broker_id == broker_id)

    if campaign_id:
        query = query.where(Bonus.campaign_id == campaign_id)
        count_query = count_query.where(Bonus.campaign_id == campaign_id)
    if mt5_login:
        query = query.where(Bonus.mt5_login == mt5_login)
        count_query = count_query.where(Bonus.mt5_login == mt5_login)
    if bonus_type:
        query = query.where(Bonus.bonus_type == bonus_type)
        count_query = count_query.where(Bonus.bonus_type == bonus_type)
    if status_filter:
        query = query.where(Bonus.status == status_filter)
        count_query = count_query.where(Bonus.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Bonus.assigned_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for bonus, campaign_name in rows:
        item = BonusRead.model_validate(bonus)
        item.campaign_name = campaign_name
        if bonus.bonus_type == "C" and bonus.lots_required:
            item.percent_converted = round(bonus.lots_traded / bonus.lots_required * 100, 2)
        items.append(item)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{bonus_id}", response_model=BonusDetailRead)
async def get_bonus(
    bonus_id: int,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = (
        select(Bonus, Campaign.name)
        .join(Campaign, Bonus.campaign_id == Campaign.id)
        .where(Bonus.id == bonus_id)
    )
    if broker_id:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Bonus not found")

    bonus, campaign_name = row
    progress_result = await db.execute(
        select(BonusLotProgress)
        .where(BonusLotProgress.bonus_id == bonus.id)
        .order_by(BonusLotProgress.created_at.desc())
    )
    progress = progress_result.scalars().all()

    item = BonusDetailRead.model_validate(bonus)
    item.campaign_name = campaign_name
    item.lot_progress = [LotProgressRead.model_validate(p) for p in progress]
    if bonus.bonus_type == "C" and bonus.lots_required:
        item.percent_converted = round(bonus.lots_traded / bonus.lots_required * 100, 2)
    return item


@router.post("/assign", response_model=BonusRead, status_code=201)
async def assign_bonus_manual(
    body: BonusAssign,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(
        AdminRole.SUPER_ADMIN, AdminRole.CAMPAIGN_MANAGER, AdminRole.SUPPORT_AGENT
    )),
):
    broker_id = user.broker_id
    query = select(Campaign).where(Campaign.id == body.campaign_id)
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    eligible, reason = await check_eligibility(db, campaign, body.mt5_login, body.deposit_amount, broker_id=broker_id)
    if not eligible:
        raise HTTPException(status_code=400, detail=reason)

    bonus = await assign_bonus(db, campaign, body.mt5_login, body.deposit_amount, actor_id=user.id, broker_id=broker_id)
    item = BonusRead.model_validate(bonus)
    item.campaign_name = campaign.name
    return item


@router.post("/{bonus_id}/cancel", response_model=BonusRead)
async def cancel_bonus_endpoint(
    bonus_id: int,
    body: BonusCancelRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN, AdminRole.CAMPAIGN_MANAGER)),
):
    broker_id = user.broker_id
    bonus = await db.get(Bonus, bonus_id)
    if not bonus:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if broker_id and bonus.broker_id != broker_id:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if bonus.status != BonusStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Bonus is not active")

    bonus = await cancel_bonus(db, bonus, body.reason, actor_id=user.id, broker_id=broker_id)
    return BonusRead.model_validate(bonus)


@router.post("/{bonus_id}/force-convert", response_model=BonusRead)
async def force_convert(
    bonus_id: int,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN)),
):
    broker_id = user.broker_id
    bonus = await db.get(Bonus, bonus_id)
    if not bonus:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if broker_id and bonus.broker_id != broker_id:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if bonus.bonus_type != "C" or bonus.status != BonusStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Not an active Type C bonus")

    gw = gateway_registry.require_gateway(bonus.broker_id)
    remaining = bonus.bonus_amount - bonus.amount_converted
    if remaining > 0:
        await gw.remove_credit(bonus.mt5_login, remaining, "Force convert")
        await gw.deposit_to_balance(bonus.mt5_login, remaining, "Force convert")

    bonus.amount_converted = bonus.bonus_amount
    bonus.lots_traded = bonus.lots_required or bonus.lots_traded
    bonus.status = BonusStatus.CONVERTED
    await db.flush()
    return BonusRead.model_validate(bonus)


@router.post("/{bonus_id}/override-leverage", response_model=BonusRead)
async def override_leverage(
    bonus_id: int,
    body: BonusOverrideLeverage,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(AdminRole.SUPER_ADMIN)),
):
    broker_id = user.broker_id
    bonus = await db.get(Bonus, bonus_id)
    if not bonus:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if broker_id and bonus.broker_id != broker_id:
        raise HTTPException(status_code=404, detail="Bonus not found")
    if bonus.bonus_type != "A":
        raise HTTPException(status_code=400, detail="Not a Type A bonus")

    gw = gateway_registry.require_gateway(bonus.broker_id)
    await gw.set_leverage(bonus.mt5_login, body.new_leverage)
    bonus.adjusted_leverage = body.new_leverage
    await db.flush()
    return BonusRead.model_validate(bonus)
