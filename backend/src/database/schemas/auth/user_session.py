from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import IP_ADDRESS_MAX_LENGTH, REFRESH_TOKEN_HASH_MAX_LENGTH, USER_AGENT_MAX_LENGTH


class UserSessionBase(BaseModel):
    user_agent: str | None = Field(default=None, max_length=USER_AGENT_MAX_LENGTH)
    ip_address: str | None = Field(default=None, max_length=IP_ADDRESS_MAX_LENGTH)


class UserSessionCreate(UserSessionBase):
    user_id: int
    refresh_token_hash: str = Field(min_length=1, max_length=REFRESH_TOKEN_HASH_MAX_LENGTH)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class UserSessionUpdate(BaseModel):
    refresh_token_hash: str | None = Field(default=None, min_length=1, max_length=REFRESH_TOKEN_HASH_MAX_LENGTH)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    user_agent: str | None = Field(default=None, max_length=USER_AGENT_MAX_LENGTH)
    ip_address: str | None = Field(default=None, max_length=IP_ADDRESS_MAX_LENGTH)


class UserSessionRead(UserSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
