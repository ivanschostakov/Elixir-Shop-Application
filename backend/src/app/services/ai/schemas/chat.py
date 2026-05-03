from dataclasses import dataclass

from src.database.models import AIChat
from src.integrations.ai.enums import AttachmentType


@dataclass
class _LoadedUpload:
    filename: str
    ai_filename: str
    content: bytes
    ai_content: bytes
    mime_type: str | None
    kind: AttachmentType


@dataclass
class AIChatActionResult:
    chat: AIChat
    basket_updated: bool = False
    basket_item_id: int | None = None


@dataclass
class AIChatSendResult:
    chat: AIChat
    turn_meta: dict[str, int | str | None]
    basket_updated: bool = False