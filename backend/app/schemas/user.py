from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.user import AdminRole


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: AdminRole = AdminRole.READ_ONLY


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[AdminRole] = None
    is_active: Optional[bool] = None


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: AdminRole
    is_active: bool
    broker_id: Optional[int] = None
    is_broker_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str
