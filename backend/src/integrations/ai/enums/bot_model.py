from enum import StrEnum
from sqlalchemy import Enum

class BotModel(StrEnum):
    FREE = "free"
    PREMIUM = "premium"

bot_model = Enum(
    BotModel,
    name="bot_model",
    values_callable=lambda enum: [item.value for item in enum],
)
