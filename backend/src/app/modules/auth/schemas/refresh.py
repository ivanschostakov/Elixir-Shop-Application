from pydantic import BaseModel, Field


class UserRefreshPayload(BaseModel):
    session_id: int
    refresh_token: str = Field(min_length=1)
