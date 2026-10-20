from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class StaffRead(BaseModel):
    user_id: int
    email: str | None
    name: str
    surname: str
    is_active: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    role_codes: list[str]


class StaffRolesPayload(BaseModel):
    role_codes: list[str] = Field(min_length=1)
    confirm_superadmin: bool = False


class StaffCreatePayload(StaffRolesPayload):
    email: EmailStr


class StaffStatusPayload(BaseModel):
    is_active: bool
