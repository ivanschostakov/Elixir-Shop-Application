from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import REQUISITE_TITLE_MAX_LENGTH


class RequisiteBase(BaseModel):
    title: str = Field(min_length=1, max_length=REQUISITE_TITLE_MAX_LENGTH)
    config: dict[str, str] = Field(default_factory=dict)


class RequisiteCreate(RequisiteBase):
    pass


class RequisiteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=REQUISITE_TITLE_MAX_LENGTH)
    config: dict[str, str] | None = Field(default=None)


class RequisiteRead(RequisiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
