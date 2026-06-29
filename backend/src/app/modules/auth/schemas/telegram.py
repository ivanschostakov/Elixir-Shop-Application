from pydantic import BaseModel, Field


class TelegramAuthPayload(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)


class TelegramAuthContactRequiredResponse(BaseModel):
    contact_required: bool = True
    telegram_user_id: int
    message: str = "Telegram phone contact is required"
