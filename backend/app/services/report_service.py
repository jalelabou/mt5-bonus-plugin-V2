from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bonus import Bonus, BonusStatus
from app.models.campaign import Campaign


async def get_bonus_summary(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    campaign_id: Optional[int] = None,
    broker_id: Optional[int] = None,
) -> List[dict]:
    query = (
        select(
            Campaign.id,
            Campaign.name,
            Campaign.bonus_type,
            func.count(Bonus.id).label("total_issued"),
            func.coalesce(func.sum(Bonus.bonus_amount), 0).label("total_amount"),
            func.count(Bonus.id).filter(Bonus.status == BonusStatus.ACTIVE).label("active_count"),
            func.count(Bonus.id).filter(Bonus.status == BonusStatus.CANCELLED).label("cancelled_count"),
            func.count(Bonus.id).filter(Bonus.status == BonusStatus.EXPIRED).label("expired_count"),
            func.count(Bonus.id).filter(Bonus.status == BonusStatus.CONVERTED).label("converted_count"),
        )
        .join(Bonus, Bonus.campaign_id == Campaign.id)
        .group_by(Campaign.id, Campaign.name, Campaign.bonus_type)
    )

    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    if date_from:
        query = query.where(Bonus.assigned_at >= date_from)
    if date_to:
        query = query.where(Bonus.assigned_at <= date_to)
    if campaign_id:
        query = query.where(Campaign.id == campaign_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "campaign_id": r[0],
            "campaign_name": r[1],
            "bonus_type": r[2].value if r[2] else None,
            "total_issued": r[3],
            "total_amount": float(r[4]),
            "active_count": r[5],
            "cancelled_count": r[6],
            "expired_count": r[7],
            "converted_count": r[8],
        }
        for r in rows
    ]


async def get_conversion_progress(
    db: AsyncSession,
    campaign_id: Optional[int] = None,
    broker_id: Optional[int] = None,
) -> List[dict]:
    query = (
        select(Bonus, Campaign.name)
        .join(Campaign, Bonus.campaign_id == Campaign.id)
        .where(Bonus.bonus_type == "C", Bonus.status == BonusStatus.ACTIVE)
    )
    if broker_id:
        query = query.where(Bonus.broker_id == broker_id)
    if campaign_id:
        query = query.where(Bonus.campaign_id == campaign_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "bonus_id": bonus.id,
            "mt5_login": bonus.mt5_login,
            "campaign_name": name,
            "bonus_amount": bonus.bonus_amount,
            "lots_required": bonus.lots_required or 0,
            "lots_traded": bonus.lots_traded,
            "percent_complete": (
                (bonus.lots_traded / bonus.lots_required * 100)
                if bonus.lots_required
                else 0
            ),
            "amount_converted": bonus.amount_converted,
            "amount_remaining": bonus.bonus_amount - bonus.amount_converted,
        }
        for bonus, name in rows
    ]


async def get_cancellation_report(
    db: AsyncSession,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    broker_id: Optional[int] = None,
) -> List[dict]:
    query = (
        select(Bonus, Campaign.name)
        .join(Campaign, Bonus.campaign_id == Campaign.id)
        .where(Bonus.status == BonusStatus.CANCELLED)
    )
    if broker_id:
        query = query.where(Bonus.broker_id == broker_id)
    if date_from:
        query = query.where(Bonus.cancelled_at >= date_from)
    if date_to:
        query = query.where(Bonus.cancelled_at <= date_to)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "bonus_id": bonus.id,
            "mt5_login": bonus.mt5_login,
            "campaign_name": name,
            "bonus_amount": bonus.bonus_amount,
            "reason": bonus.cancellation_reason or "unknown",
            "cancelled_at": bonus.cancelled_at.isoformat() if bonus.cancelled_at else None,
        }
        for bonus, name in rows
    ]


async def get_leverage_report(
    db: AsyncSession,
    broker_id: Optional[int] = None,
) -> List[dict]:
    query = (
        select(Bonus, Campaign.name)
        .join(Campaign, Bonus.campaign_id == Campaign.id)
        .where(Bonus.bonus_type == "A", Bonus.original_leverage.isnot(None))
    )
    if broker_id:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "bonus_id": bonus.id,
            "mt5_login": bonus.mt5_login,
            "campaign_name": name,
            "original_leverage": bonus.original_leverage,
            "adjusted_leverage": bonus.adjusted_leverage,
            "status": bonus.status.value,
        }
        for bonus, name in rows
    ]
