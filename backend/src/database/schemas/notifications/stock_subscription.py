from pydantic import BaseModel


class ProductStockSubscriptionStatusRead(BaseModel):
    product_id: int
    is_subscribed: bool
