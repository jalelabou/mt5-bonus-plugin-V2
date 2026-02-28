from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.broker import Broker
from app.services.trigger_service import (
    process_deposit_trigger,
    process_promo_code_trigger,
    process_registration_trigger,
)

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


class DepositEvent(BaseModel):
    mt5_login: str
    deposit_amount: float
    agent_code: Optional[str] = None


class RegistrationEvent(BaseModel):
    mt5_login: str


class PromoCodeEvent(BaseModel):
    mt5_login: str
    promo_code: str
    deposit_amount: Optional[float] = None


async def _get_broker_from_api_key(
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Broker:
    """Authenticate via X-API-Key header and return the broker."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    result = await db.execute(
        select(Broker).where(Broker.api_key == x_api_key, Broker.is_active == True)
    )
    broker = result.scalar_one_or_none()
    if not broker:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return broker


@router.post("/deposit")
async def deposit_trigger(
    body: DepositEvent,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(_get_broker_from_api_key),
):
    results = await process_deposit_trigger(
        db, body.mt5_login, body.deposit_amount, body.agent_code, broker_id=broker.id
    )
    return {"results": results}


@router.post("/registration")
async def registration_trigger(
    body: RegistrationEvent,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(_get_broker_from_api_key),
):
    results = await process_registration_trigger(db, body.mt5_login, broker_id=broker.id)
    return {"results": results}


@router.post("/promo-code")
async def promo_code_trigger(
    body: PromoCodeEvent,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(_get_broker_from_api_key),
):
    results = await process_promo_code_trigger(
        db, body.mt5_login, body.promo_code, body.deposit_amount, broker_id=broker.id
    )
    return {"results": results}
