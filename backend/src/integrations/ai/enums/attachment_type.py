from enum import StrEnum
from sqlalchemy import Enum


class AttachmentType(StrEnum):
    DOCUMENT = "document"
    IMAGE = "image"


attachment_type = Enum(
    AttachmentType,
    name="attachment_type",
    values_callable=lambda enum: [item.value for item in enum],
)