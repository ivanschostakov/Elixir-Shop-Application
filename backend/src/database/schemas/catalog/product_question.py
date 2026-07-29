from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductQuestionCreate(BaseModel):
    text: str = Field(min_length=3, max_length=2000)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Question must contain at least 3 characters")
        return normalized


class ProductQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_username: str
    product_id: int
    text: str
    answer: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductQuestionListRead(BaseModel):
    items: list[ProductQuestionRead]
    total: int = Field(ge=0)
