from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FavouredProductBase(BaseModel):
    user_id: int
    product_id: int


class FavouredProductCreate(FavouredProductBase):
    pass


class FavouredProductUpdate(BaseModel):
    user_id: int | None = None
    product_id: int | None = None


class FavouredProductRead(FavouredProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FavouriteProductStatusRead(BaseModel):
    product_id: int
    is_favoured: bool
