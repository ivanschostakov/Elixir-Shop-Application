from enum import StrEnum
from sqlalchemy import Enum


class MessageSender(StrEnum):
    USER = "user"
    AI = "ai"

message_sender = Enum(
    MessageSender,
    name="message_sender",
    values_callable=lambda enum: [item.value for item in enum],
)
