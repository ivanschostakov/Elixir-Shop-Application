from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockNotificationSubscriptionUpsert(BaseModel):
    variant_id: int = Field(ge=1)


class StockNotificationSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    variant_id: int
    is_active: bool
    last_seen_stock: int
    notified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StockNotificationSubscriptionDeleteResponse(BaseModel):
    ok: bool
