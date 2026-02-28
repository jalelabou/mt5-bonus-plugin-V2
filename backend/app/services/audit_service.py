from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import ActorType, AuditLog, EventType


async def log_event(
    db: AsyncSession,
    event_type: EventType,
    mt5_login: Optional[str] = None,
    campaign_id: Optional[int] = None,
    bonus_id: Optional[int] = None,
    actor_type: ActorType = ActorType.SYSTEM,
    actor_id: Optional[int] = None,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
    metadata: Optional[dict] = None,
    broker_id: Optional[int] = None,
):
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        mt5_login=mt5_login,
        campaign_id=campaign_id,
        bonus_id=bonus_id,
        event_type=event_type,
        before_state=before_state,
        after_state=after_state,
        metadata_=metadata,
        broker_id=broker_id,
    )
    db.add(entry)
    await db.flush()
    return entry
