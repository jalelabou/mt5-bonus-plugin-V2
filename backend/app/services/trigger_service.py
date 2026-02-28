from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignStatus, TriggerType
from app.models.trigger import TriggerEvent, TriggerStatus
from app.services.bonus_engine import assign_bonus, check_eligibility


async def process_deposit_trigger(
    db: AsyncSession,
    mt5_login: str,
    deposit_amount: float,
    agent_code: Optional[str] = None,
    broker_id: Optional[int] = None,
) -> List[dict]:
    results = []
    campaigns = await _get_active_campaigns_for_trigger("auto_deposit", db, broker_id=broker_id)

    for campaign in campaigns:
        # Also check agent code campaigns
        if agent_code:
            agent_campaigns = await _get_active_campaigns_for_trigger("agent_code", db, broker_id=broker_id)
            for ac in agent_campaigns:
                if ac.agent_codes and agent_code in ac.agent_codes and ac.id != campaign.id:
                    campaigns.append(ac)

        eligible, reason = await check_eligibility(db, campaign, mt5_login, deposit_amount, broker_id=broker_id)

        trigger_event = TriggerEvent(
            broker_id=broker_id or campaign.broker_id,
            campaign_id=campaign.id,
            mt5_login=mt5_login,
            trigger_type="auto_deposit",
            event_data={"deposit_amount": deposit_amount, "agent_code": agent_code},
        )

        if eligible:
            try:
                bonus = await assign_bonus(db, campaign, mt5_login, deposit_amount, broker_id=broker_id)
                trigger_event.status = TriggerStatus.PROCESSED
                trigger_event.processed_at = datetime.now(timezone.utc)
                results.append({"campaign_id": campaign.id, "bonus_id": bonus.id, "status": "assigned"})
            except Exception as e:
                trigger_event.status = TriggerStatus.FAILED
                trigger_event.skip_reason = str(e)
                results.append({"campaign_id": campaign.id, "status": "failed", "error": str(e)})
        else:
            trigger_event.status = TriggerStatus.SKIPPED
            trigger_event.skip_reason = reason
            results.append({"campaign_id": campaign.id, "status": "skipped", "reason": reason})

        db.add(trigger_event)

    await db.flush()
    return results


async def process_registration_trigger(
    db: AsyncSession,
    mt5_login: str,
    broker_id: Optional[int] = None,
) -> List[dict]:
    results = []
    campaigns = await _get_active_campaigns_for_trigger("registration", db, broker_id=broker_id)

    for campaign in campaigns:
        eligible, reason = await check_eligibility(db, campaign, mt5_login, broker_id=broker_id)

        trigger_event = TriggerEvent(
            broker_id=broker_id or campaign.broker_id,
            campaign_id=campaign.id,
            mt5_login=mt5_login,
            trigger_type="registration",
            event_data={},
        )

        if eligible:
            try:
                bonus = await assign_bonus(db, campaign, mt5_login, deposit_amount=0, broker_id=broker_id)
                trigger_event.status = TriggerStatus.PROCESSED
                trigger_event.processed_at = datetime.now(timezone.utc)
                results.append({"campaign_id": campaign.id, "bonus_id": bonus.id, "status": "assigned"})
            except Exception as e:
                trigger_event.status = TriggerStatus.FAILED
                trigger_event.skip_reason = str(e)
                results.append({"campaign_id": campaign.id, "status": "failed", "error": str(e)})
        else:
            trigger_event.status = TriggerStatus.SKIPPED
            trigger_event.skip_reason = reason
            results.append({"campaign_id": campaign.id, "status": "skipped", "reason": reason})

        db.add(trigger_event)

    await db.flush()
    return results


async def process_promo_code_trigger(
    db: AsyncSession,
    mt5_login: str,
    promo_code: str,
    deposit_amount: Optional[float] = None,
    broker_id: Optional[int] = None,
) -> List[dict]:
    results = []
    query = select(Campaign).where(
        Campaign.status == CampaignStatus.ACTIVE,
        Campaign.promo_code == promo_code,
    )
    if broker_id is not None:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    campaigns = result.scalars().all()

    for campaign in campaigns:
        eligible, reason = await check_eligibility(db, campaign, mt5_login, deposit_amount, broker_id=broker_id)

        trigger_event = TriggerEvent(
            broker_id=broker_id or campaign.broker_id,
            campaign_id=campaign.id,
            mt5_login=mt5_login,
            trigger_type="promo_code",
            event_data={"promo_code": promo_code, "deposit_amount": deposit_amount},
        )

        if eligible:
            try:
                bonus = await assign_bonus(db, campaign, mt5_login, deposit_amount, broker_id=broker_id)
                trigger_event.status = TriggerStatus.PROCESSED
                trigger_event.processed_at = datetime.now(timezone.utc)
                results.append({"campaign_id": campaign.id, "bonus_id": bonus.id, "status": "assigned"})
            except Exception as e:
                trigger_event.status = TriggerStatus.FAILED
                trigger_event.skip_reason = str(e)
                results.append({"campaign_id": campaign.id, "status": "failed", "error": str(e)})
        else:
            trigger_event.status = TriggerStatus.SKIPPED
            trigger_event.skip_reason = reason
            results.append({"campaign_id": campaign.id, "status": "skipped", "reason": reason})

        db.add(trigger_event)

    await db.flush()
    return results


async def _get_active_campaigns_for_trigger(
    trigger_type: str, db: AsyncSession, broker_id: Optional[int] = None,
) -> List[Campaign]:
    query = select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
    if broker_id is not None:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    all_active = result.scalars().all()
    return [c for c in all_active if trigger_type in (c.trigger_types or [])]
