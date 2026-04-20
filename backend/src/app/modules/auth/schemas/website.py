from pydantic import BaseModel, Field


class WebsiteIdentityLoginPayload(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
