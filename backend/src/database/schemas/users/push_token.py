from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.database.limits import EXTERNAL_ID_MAX_LENGTH, STATUS_MAX_LENGTH

PushTokenPlatform = Literal["ios", "android"]


class UserPushTokenUpsert(BaseModel):
    expo_push_token: str = Field(min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH)
    platform: PushTokenPlatform | None = Field(default=None)

    @field_validator("expo_push_token")
    @classmethod
    def strip_expo_push_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("expo_push_token must not be empty")
        return normalized


class UserPushTokenDelete(BaseModel):
    expo_push_token: str = Field(min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH)

    @field_validator("expo_push_token")
    @classmethod
    def strip_expo_push_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("expo_push_token must not be empty")
        return normalized


class UserPushTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    expo_push_token: str = Field(max_length=EXTERNAL_ID_MAX_LENGTH)
    platform: str | None = Field(default=None, max_length=STATUS_MAX_LENGTH)
    created_at: datetime
    updated_at: datetime


class UserPushTokenDeleteResponse(BaseModel):
    ok: bool
