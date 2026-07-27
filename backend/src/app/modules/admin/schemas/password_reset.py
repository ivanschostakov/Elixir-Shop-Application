from pydantic import BaseModel, EmailStr, Field


class AdminPasswordResetRequest(BaseModel):
    email: EmailStr


class AdminPasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)
