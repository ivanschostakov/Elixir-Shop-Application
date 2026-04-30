from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.integrations.ai.enums import AttachmentType


class AIAttachmentBase(BaseModel):
    type: AttachmentType
    original_filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    size_bytes: int = Field(ge=0)


class AIAttachmentCreate(AIAttachmentBase):
    message_id: int = Field(ge=1)
    filename: str | None = Field(default=None, min_length=1, max_length=255)


class AIAttachmentUpdate(BaseModel):
    type: AttachmentType | None = None
    original_filename: str | None = Field(default=None, max_length=255)
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    size_bytes: int | None = Field(default=None, ge=0)


class AIAttachmentRead(AIAttachmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    filename: str
    relative_path: Path
    created_at: datetime
    updated_at: datetime
