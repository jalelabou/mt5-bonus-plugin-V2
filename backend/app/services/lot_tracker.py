from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.interface import MT5Deal
from app.gateway.registry import gateway_registry
from app.models.audit_log import EventType
from app.models.bonus import Bonus, BonusLotProgress, BonusStatus
from app.models.campaign import Campaign, LotTrackingScope
from app.services.audit_service import log_event


async def process_deal(db: AsyncSession, bonus: Bonus, deal: MT5Deal, broker_id: Optional[int] = None) -> bool:
    if bonus.status != BonusStatus.ACTIVE or bonus.bonus_type != "C":
        return False

    _broker_id = broker_id or bonus.broker_id
    gw = gateway_registry.require_gateway(_broker_id)

    campaign = await db.get(Campaign, bonus.campaign_id)
    if not campaign:
        return False

    # Check lot tracking scope
    if not _is_deal_eligible(campaign, bonus, deal):
        return False

    # Calculate conversion amount
    if not bonus.lots_required or bonus.lots_required <= 0:
        return False

    conversion_per_lot = bonus.bonus_amount / bonus.lots_required
    convert_amount = deal.volume_lots * conversion_per_lot

    remaining_credit = bonus.bonus_amount - bonus.amount_converted
    if convert_amount > remaining_credit:
        convert_amount = remaining_credit

    if convert_amount <= 0:
        return False

    # Execute conversion: remove credit, add to balance
    await gw.remove_credit(bonus.mt5_login, convert_amount, f"Convert lot {deal.deal_id}")
    await gw.deposit_to_balance(bonus.mt5_login, convert_amount, f"Convert lot {deal.deal_id}")

    # Record progress
    progress = BonusLotProgress(
        broker_id=_broker_id,
        bonus_id=bonus.id,
        deal_id=deal.deal_id,
        symbol=deal.symbol,
        lots=deal.volume_lots,
        amount_converted=convert_amount,
    )
    db.add(progress)

    bonus.lots_traded += deal.volume_lots
    bonus.amount_converted += convert_amount

    # Check if fully converted
    if bonus.amount_converted >= bonus.bonus_amount - 0.01:
        bonus.status = BonusStatus.CONVERTED
        bonus.amount_converted = bonus.bonus_amount

    await db.flush()

    await log_event(
        db,
        event_type=EventType.CONVERSION_STEP,
        mt5_login=bonus.mt5_login,
        campaign_id=bonus.campaign_id,
        bonus_id=bonus.id,
        after_state={
            "deal_id": deal.deal_id,
            "lots": deal.volume_lots,
            "amount_converted": convert_amount,
            "total_converted": bonus.amount_converted,
            "total_lots": bonus.lots_traded,
            "fully_converted": bonus.status == BonusStatus.CONVERTED,
        },
        broker_id=_broker_id,
    )
    return True


async def handle_withdrawal(db: AsyncSession, bonus: Bonus, withdrawal_amount: float, broker_id: Optional[int] = None) -> bool:
    if bonus.status != BonusStatus.ACTIVE or bonus.bonus_type != "C":
        return False

    _broker_id = broker_id or bonus.broker_id
    gw = gateway_registry.require_gateway(_broker_id)

    remaining_credit = bonus.bonus_amount - bonus.amount_converted
    if remaining_credit <= 0:
        return False

    before_state = {
        "status": bonus.status.value,
        "amount_converted": bonus.amount_converted,
        "remaining_credit": remaining_credit,
    }

    await gw.remove_credit(
        bonus.mt5_login, remaining_credit, f"Withdrawal cancellation"
    )

    bonus.status = BonusStatus.CANCELLED
    bonus.cancelled_at = datetime.now(timezone.utc)
    bonus.cancellation_reason = f"withdrawal_triggered:{withdrawal_amount}"
    await db.flush()

    await log_event(
        db,
        event_type=EventType.CANCELLATION,
        mt5_login=bonus.mt5_login,
        campaign_id=bonus.campaign_id,
        bonus_id=bonus.id,
        before_state=before_state,
        after_state={
            "status": "cancelled",
            "reason": "withdrawal",
            "withdrawal_amount": withdrawal_amount,
            "cancelled_credit": remaining_credit,
        },
        broker_id=_broker_id,
    )
    return True


def _is_deal_eligible(campaign: Campaign, bonus: Bonus, deal: MT5Deal) -> bool:
    scope = campaign.lot_tracking_scope

    if scope == LotTrackingScope.SYMBOL_FILTERED:
        if campaign.symbol_filter and deal.symbol not in campaign.symbol_filter:
            return False

    if scope == LotTrackingScope.PER_TRADE_THRESHOLD:
        if campaign.per_trade_lot_minimum and deal.volume_lots < campaign.per_trade_lot_minimum:
            return False

    if scope == LotTrackingScope.POST_BONUS:
        if deal.timestamp < bonus.assigned_at.timestamp():
            return False

    return True
