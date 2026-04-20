from pydantic import BaseModel, Field


class CDEKCalculatedDelivery(BaseModel):
    delivery_sum: float = Field(..., description="The sum of the delivery price")
    period_min: int = Field(..., description="The minimum delivery period, in days")
    period_max: int = Field(..., description="The maximum delivery period, in days")
    weight_calc: int = Field(..., description="The calculated weight of the delivery")
    currency: str = Field(..., description="The currency of the delivery price")
