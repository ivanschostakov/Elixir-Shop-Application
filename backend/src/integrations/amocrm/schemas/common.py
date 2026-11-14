from typing import Literal
from pydantic import BaseModel, ConfigDict


class AmoBaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class AmoValue(AmoBaseSchema):
    value: str | int | float | None = None
    enum_code: str | None = None
    enum_id: int | None = None


class AmoCustomFieldByCode(AmoBaseSchema):
    field_code: Literal["PHONE", "EMAIL"]
    values: list[AmoValue]


class AmoCustomFieldById(AmoBaseSchema):
    field_id: int
    values: list[AmoValue]
