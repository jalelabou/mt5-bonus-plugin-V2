from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.database import get_db
from app.models.bonus import Bonus, BonusStatus
from app.models.campaign import Campaign, CampaignStatus
from app.models.user import AdminRole, AdminUser
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListRead,
    CampaignRead,
    CampaignStatusUpdate,
    CampaignUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

WRITE_ROLES = (AdminRole.SUPER_ADMIN, AdminRole.CAMPAIGN_MANAGER)


@router.get("", response_model=PaginatedResponse[CampaignListRead])
async def list_campaigns(
    status_filter: Optional[CampaignStatus] = Query(None, alias="status"),
    bonus_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = select(Campaign)
    count_query = select(func.count(Campaign.id))

    # Scope to broker
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
        count_query = count_query.where(Campaign.broker_id == broker_id)

    if status_filter:
        query = query.where(Campaign.status == status_filter)
        count_query = count_query.where(Campaign.status == status_filter)
    if bonus_type:
        query = query.where(Campaign.bonus_type == bonus_type)
        count_query = count_query.where(Campaign.bonus_type == bonus_type)
    if search:
        query = query.where(Campaign.name.ilike(f"%{search}%"))
        count_query = count_query.where(Campaign.name.ilike(f"%{search}%"))

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Campaign.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    campaigns = result.scalars().all()

    items = []
    for c in campaigns:
        bonus_count_q = select(func.count(Bonus.id)).where(
            Bonus.campaign_id == c.id, Bonus.status == BonusStatus.ACTIVE
        )
        active_count = (await db.execute(bonus_count_q)).scalar() or 0
        item = CampaignListRead.model_validate(c)
        item.active_bonus_count = active_count
        items.append(item)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(*WRITE_ROLES)),
):
    broker_id = user.broker_id
    if not broker_id:
        raise HTTPException(status_code=400, detail="No broker context")
    campaign = Campaign(**body.model_dump(), created_by_id=user.id, broker_id=broker_id)
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return CampaignRead.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    broker_id = user.broker_id
    query = select(Campaign).where(Campaign.id == campaign_id)
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    bonus_count_q = select(func.count(Bonus.id)).where(
        Bonus.campaign_id == campaign.id, Bonus.status == BonusStatus.ACTIVE
    )
    active_count = (await db.execute(bonus_count_q)).scalar() or 0
    resp = CampaignRead.model_validate(campaign)
    resp.active_bonus_count = active_count
    return resp


@router.put("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(*WRITE_ROLES)),
):
    broker_id = user.broker_id
    query = select(Campaign).where(Campaign.id == campaign_id)
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign)
    return CampaignRead.model_validate(campaign)


@router.post("/{campaign_id}/duplicate", response_model=CampaignRead, status_code=201)
async def duplicate_campaign(
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(*WRITE_ROLES)),
):
    broker_id = user.broker_id
    query = select(Campaign).where(Campaign.id == campaign_id)
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Campaign not found")

    data = {
        c.name: getattr(original, c.name)
        for c in Campaign.__table__.columns
        if c.name not in ("id", "created_at", "updated_at", "created_by_id", "status")
    }
    data["name"] = f"{original.name} (Copy)"
    data["status"] = CampaignStatus.DRAFT
    data["created_by_id"] = user.id

    new_campaign = Campaign(**data)
    db.add(new_campaign)
    await db.flush()
    await db.refresh(new_campaign)
    return CampaignRead.model_validate(new_campaign)


@router.patch("/{campaign_id}/status", response_model=CampaignRead)
async def update_campaign_status(
    campaign_id: int,
    body: CampaignStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_roles(*WRITE_ROLES)),
):
    broker_id = user.broker_id
    query = select(Campaign).where(Campaign.id == campaign_id)
    if broker_id:
        query = query.where(Campaign.broker_id == broker_id)
    result = await db.execute(query)
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = body.status
    await db.flush()
    await db.refresh(campaign)
    return CampaignRead.model_validate(campaign)
