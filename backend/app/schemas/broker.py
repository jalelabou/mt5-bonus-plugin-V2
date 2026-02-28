from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BrokerCreate(BaseModel):
    name: str
    slug: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    mt5_bridge_url: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_manager_login: Optional[str] = None
    mt5_manager_password: Optional[str] = None


class BrokerUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    mt5_bridge_url: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_manager_login: Optional[str] = None
    mt5_manager_password: Optional[str] = None


class BrokerRead(BaseModel):
    id: int
    name: str
    slug: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    mt5_bridge_url: Optional[str] = None
    mt5_server: Optional[str] = None
    mt5_manager_login: Optional[str] = None
    api_key: Optional[str] = None
    is_active: bool
    mt5_configured: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrokerAdminCreate(BaseModel):
    email: str
    password: str
    full_name: str
