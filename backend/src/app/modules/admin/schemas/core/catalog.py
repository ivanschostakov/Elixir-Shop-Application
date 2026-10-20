from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AdminVariantRead(BaseModel):
    id: int
    system_id: str
    sku: str | None
    name: str
    stock: int
    display_stock: int
    price: Decimal
    archived: bool
    image_url: str


class AdminProductRead(BaseModel):
    id: int
    system_id: str
    sku: str
    name: str
    description: str | None
    usage: str | None
    expiration: str | None
    in_stock: bool
    archived: bool
    is_visible_in_app: bool
    priority: int
    is_new_manual: bool
    is_new: bool
    discount_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    effective_discount_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    stock_reduction_override: int | None
    effective_stock_reduction: int
    image_url: str
    category_ids: list[int]
    variants: list[AdminVariantRead]
    created_at: datetime
    updated_at: datetime


class AdminProductMerchandisePayload(BaseModel):
    description: str | None = None
    usage: str | None = None
    expiration: str | None = None
    priority: int = Field(ge=0)
    is_new_manual: bool | None = None
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    stock_reduction_override: int | None = Field(default=None, ge=0, le=1_000_000)
    category_ids: list[int] = Field(default_factory=list)
    expected_updated_at: datetime


class AdminProductVisibilityPayload(BaseModel):
    is_visible_in_app: bool
    expected_updated_at: datetime


class AdminCatalogStockSettingsRead(BaseModel):
    enabled: bool
    reduction: int
    updated_at: datetime | None


class AdminCatalogStockSettingsPayload(BaseModel):
    enabled: bool
    reduction: int = Field(ge=0, le=1_000_000)


class AdminCategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    archived: bool = False
    is_visible_in_app: bool = True
    app_display_order: int = Field(default=10_000, ge=0)
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2)


class AdminCategoryRead(AdminCategoryPayload):
    id: int
    created_at: datetime
    updated_at: datetime
