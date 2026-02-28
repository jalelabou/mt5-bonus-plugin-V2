from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.audit_log import AuditLog, EventType
from app.models.user import AdminUser
from app.schemas.audit_log import AuditLogRead
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=PaginatedResponse[AuditLogRead])
async def list_audit_logs(
    mt5_login: Optional[str] = None,
    campaign_id: Optional[int] = None,
    bonus_id: Optional[int] = None,
    event_type: Optional[EventType] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    # Scope to broker
    if broker_id:
        query = query.where(AuditLog.broker_id == broker_id)
        count_query = count_query.where(AuditLog.broker_id == broker_id)

    if mt5_login:
        query = query.where(AuditLog.mt5_login == mt5_login)
        count_query = count_query.where(AuditLog.mt5_login == mt5_login)
    if campaign_id:
        query = query.where(AuditLog.campaign_id == campaign_id)
        count_query = count_query.where(AuditLog.campaign_id == campaign_id)
    if bonus_id:
        query = query.where(AuditLog.bonus_id == bonus_id)
        count_query = count_query.where(AuditLog.bonus_id == bonus_id)
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
        count_query = count_query.where(AuditLog.event_type == event_type)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
        count_query = count_query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
        count_query = count_query.where(AuditLog.created_at <= date_to)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [AuditLogRead.model_validate(log) for log in result.scalars().all()]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )
