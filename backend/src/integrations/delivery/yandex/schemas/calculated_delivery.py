from decimal import Decimal
from pydantic import BaseModel, Field, computed_field

class YandexCalculatedDelivery(BaseModel):
    delivery_days: int = Field(..., description="Number of delivery days")
    pricing_total: str = Field(..., description="Pricing total")

    @computed_field
    @property
    def price(self) -> Decimal: return Decimal(self.pricing_total.removesuffix(" RUB"))