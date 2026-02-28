from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.interface import MT5Deal
from app.models.bonus import Bonus, BonusStatus
from app.services.lot_tracker import handle_withdrawal, process_deal


async def process_deal_event(db: AsyncSession, deal: MT5Deal, broker_id: Optional[int] = None):
    query = select(Bonus).where(
        Bonus.mt5_login == deal.login,
        Bonus.status == BonusStatus.ACTIVE,
        Bonus.bonus_type == "C",
    )
    if broker_id is not None:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    bonuses = result.scalars().all()

    for bonus in bonuses:
        await process_deal(db, bonus, deal, broker_id=broker_id)


async def process_withdrawal_event(db: AsyncSession, mt5_login: str, amount: float, broker_id: Optional[int] = None):
    from app.services.bonus_engine import cancel_bonus

    query = select(Bonus).where(
        Bonus.mt5_login == mt5_login,
        Bonus.status == BonusStatus.ACTIVE,
    )
    if broker_id is not None:
        query = query.where(Bonus.broker_id == broker_id)
    result = await db.execute(query)
    bonuses = result.scalars().all()

    for bonus in bonuses:
        if bonus.bonus_type == "C":
            await handle_withdrawal(db, bonus, amount, broker_id=broker_id)
        else:
            await cancel_bonus(db, bonus, reason=f"withdrawal:{amount:.2f}", broker_id=broker_id)
