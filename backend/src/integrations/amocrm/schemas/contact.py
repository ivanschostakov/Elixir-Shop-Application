from pydantic import Field
from .common import AmoBaseSchema, AmoCustomFieldByCode

class ContactCreatePayload(AmoBaseSchema):
    name: str
    custom_fields_values: list[AmoCustomFieldByCode] = Field(default_factory=list)

class ContactUpdatePayload(AmoBaseSchema):
    id: int
    name: str | None = None
    custom_fields_values: list[AmoCustomFieldByCode] | None = None
    