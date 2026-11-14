from pydantic import Field
from .common import AmoBaseSchema, AmoCustomFieldById

class LeadTagPayload(AmoBaseSchema):
    name: str

class LeadContact(AmoBaseSchema):
    id: int

class LeadEmbedded(AmoBaseSchema):
    contacts: list[LeadContact]

class LeadCreatePayload(AmoBaseSchema):
    name: str
    pipeline_id: int
    status_id: int
    price: int | None = None
    custom_fields_values: list[AmoCustomFieldById] = Field(default_factory=list)
    tags_to_add: list[LeadTagPayload] | None = None
    embedded: LeadEmbedded | None = Field(default=None, serialization_alias="_embedded")

class LeadStatusUpdatePayload(AmoBaseSchema):
    id: int
    pipeline_id: int
    status_id: int

class LeadLinkPayload(AmoBaseSchema):
    to_entity_id: int
    to_entity_type: str = "contacts"

class LeadNoteParams(AmoBaseSchema):
    text: str

class LeadNoteCreatePayload(AmoBaseSchema):
    entity_id: int
    note_type: str = "common"
    params: LeadNoteParams
