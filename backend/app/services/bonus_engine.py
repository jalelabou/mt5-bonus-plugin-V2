from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.registry import gateway_registry
from app.models.audit_log import ActorType, EventType
from app.models.bonus import Bonus, BonusStatus
from app.models.campaign import Campaign, CampaignStatus
from app.services.audit_service import log_event
from app.services.leverage_service import apply_leverage_reduction, restore_leverage


async def assign_bonus(
    db: AsyncSession,
    campaign: Campaign,
    mt5_login: str,
    deposit_amount: Optional[float] = None,
    actor_id: Optional[int] = None,
    broker_id: Optional[int] = None,
) -> Bonus:
    _broker_id = broker_id or campaign.broker_id
    gw = gateway_registry.require_gateway(_broker_id)

    account = await gw.get_account_info(mt5_login)
    if not account:
        raise ValueError(f"MT5 account {mt5_login} not found")

    # Calculate bonus amount
    base_amount = deposit_amount if deposit_amount else account.balance
    bonus_amount = base_amount * (campaign.bonus_percentage / 100.0)

    if campaign.max_bonus_amount and bonus_amount > campaign.max_bonus_amount:
        bonus_amount = campaign.max_bonus_amount

    # Post credit to MT5
    success = await gw.post_credit(mt5_login, bonus_amount, f"Bonus: {campaign.name}")
    if not success:
        raise RuntimeError(f"Failed to post credit to {mt5_login}")

    # Handle leverage for Type A
    original_leverage = None
    adjusted_leverage = None
    if campaign.bonus_type.value == "A":
        original_leverage = account.leverage
        adjusted_leverage = await apply_leverage_reduction(
            gw, mt5_login, original_leverage, campaign.bonus_percentage
        )

    # Calculate expiry
    expires_at = None
    if campaign.expiry_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=campaign.expiry_days)

    now = datetime.now(timezone.utc)
    bonus = Bonus(
        broker_id=_broker_id,
        campaign_id=campaign.id,
        mt5_login=mt5_login,
        bonus_type=campaign.bonus_type.value,
        bonus_amount=bonus_amount,
        original_leverage=original_leverage,
        adjusted_leverage=adjusted_leverage,
        lots_required=campaign.lot_requirement if campaign.bonus_type.value == "C" else None,
        lots_traded=0.0,
        amount_converted=0.0,
        status=BonusStatus.ACTIVE,
        assigned_at=now,
        expires_at=expires_at,
    )
    db.add(bonus)
    await db.flush()
    await db.refresh(bonus)

    await log_event(
        db,
        event_type=EventType.ASSIGNMENT,
        mt5_login=mt5_login,
        campaign_id=campaign.id,
        bonus_id=bonus.id,
        actor_type=ActorType.ADMIN if actor_id else ActorType.SYSTEM,
        actor_id=actor_id,
        after_state={
            "bonus_amount": bonus_amount,
            "bonus_type": campaign.bonus_type.value,
            "original_leverage": original_leverage,
            "adjusted_leverage": adjusted_leverage,
        },
        broker_id=_broker_id,
    )

    # Auto-register for monitoring
    from app.services.monitor_service import register_for_monitoring
    await register_for_monitoring(db, mt5_login, reason="active_bonus", broker_id=_broker_id)

    return bonus


async def cancel_bonus(
    db: AsyncSession,
    bonus: Bonus,
    reason: str = "admin_cancel",
    actor_id: Optional[int] = None,
    broker_id: Optional[int] = None,
) -> Bonus:
    _broker_id = broker_id or bonus.broker_id
    gw = gateway_registry.require_gateway(_broker_id)

    before_state = {
        "status": bonus.status.value,
        "bonus_amount": bonus.bonus_amount,
        "amount_converted": bonus.amount_converted,
    }

    remaining_credit = bonus.bonus_amount - bonus.amount_converted
    if remaining_credit > 0:
        await gw.remove_credit(bonus.mt5_login, remaining_credit, f"Cancel: {reason}")

    if bonus.bonus_type == "A" and bonus.original_leverage:
        await restore_leverage(gw, bonus.mt5_login, bonus.original_leverage)
        await log_event(
            db,
            event_type=EventType.LEVERAGE_CHANGE,
            mt5_login=bonus.mt5_login,
            campaign_id=bonus.campaign_id,
            bonus_id=bonus.id,
            before_state={"leverage": bonus.adjusted_leverage},
            after_state={"leverage": bonus.original_leverage},
            broker_id=_broker_id,
        )

    bonus.status = BonusStatus.CANCELLED
    bonus.cancelled_at = datetime.now(timezone.utc)
    bonus.cancellation_reason = reason
    await db.flush()

    await log_event(
        db,
        event_type=EventType.CANCELLATION,
        mt5_login=bonus.mt5_login,
        campaign_id=bonus.campaign_id,
        bonus_id=bonus.id,
        actor_type=ActorType.ADMIN if actor_id else ActorType.SYSTEM,
        actor_id=actor_id,
        before_state=before_state,
        after_state={"status": "cancelled", "reason": reason},
        broker_id=_broker_id,
    )

    # Auto-unregister if no active bonuses remain
    from app.services.monitor_service import unregister_if_no_bonuses
    await unregister_if_no_bonuses(db, bonus.mt5_login, broker_id=_broker_id)

    return bonus


async def expire_bonus(db: AsyncSession, bonus: Bonus) -> Bonus:
    return await cancel_bonus(db, bonus, reason="expired", broker_id=bonus.broker_id)


async def check_eligibility(
    db: AsyncSession,
    campaign: Campaign,
    mt5_login: str,
    deposit_amount: Optional[float] = None,
    broker_id: Optional[int] = None,
) -> tuple[bool, str]:
    _broker_id = broker_id or campaign.broker_id
    gw = gateway_registry.require_gateway(_broker_id)

    if campaign.status != CampaignStatus.ACTIVE:
        return False, "Campaign is not active"

    if campaign.end_date:
        end = campaign.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > end:
            return False, "Campaign has ended"

    account = await gw.get_account_info(mt5_login)
    if not account:
        return False, "MT5 account not found"

    # Group targeting
    if campaign.target_mt5_groups:
        if account.group not in campaign.target_mt5_groups:
            return False, f"Account group {account.group} not in target groups"

    # Country targeting
    if campaign.target_countries:
        if account.country not in campaign.target_countries:
            return False, f"Account country {account.country} not in target countries"

    # Deposit thresholds
    if deposit_amount is not None:
        if campaign.min_deposit and deposit_amount < campaign.min_deposit:
            return False, f"Deposit {deposit_amount} below minimum {campaign.min_deposit}"
        if campaign.max_deposit and deposit_amount > campaign.max_deposit:
            return False, f"Deposit {deposit_amount} above maximum {campaign.max_deposit}"

    # One bonus per account
    if campaign.one_bonus_per_account:
        existing = await db.execute(
            select(func.count(Bonus.id)).where(
                Bonus.campaign_id == campaign.id,
                Bonus.mt5_login == mt5_login,
            )
        )
        if (existing.scalar() or 0) > 0:
            return False, "Account already received this campaign bonus"

    # Max concurrent bonuses
    active_count_q = select(func.count(Bonus.id)).where(
        Bonus.mt5_login == mt5_login, Bonus.status == BonusStatus.ACTIVE
    )
    active_count = (await db.execute(active_count_q)).scalar() or 0
    if active_count >= campaign.max_concurrent_bonuses:
        return False, f"Account has {active_count} active bonuses (max: {campaign.max_concurrent_bonuses})"

    return True, "Eligible"
