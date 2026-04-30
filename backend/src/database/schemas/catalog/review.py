from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import REVIEW_MAXIMUM_LENGTH


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    product_id: int
    value: int = Field(ge=0, le=5)
    text: str | None = Field(default=None, max_length=REVIEW_MAXIMUM_LENGTH)
    answer: str | None = Field(default=None, max_length=REVIEW_MAXIMUM_LENGTH)
    likes: int = Field(ge=0)
    dislikes: int = Field(ge=0)
    moderated: bool
    created_at: datetime
    updated_at: datetime


class ReviewCreate(BaseModel):
    value: int = Field(ge=0, le=5)
    text: str | None = Field(default=None, max_length=REVIEW_MAXIMUM_LENGTH)


class ReviewEligibilityRead(BaseModel):
    can_review: bool
