from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.database.crud import get_product_categories
from src.database.schemas import ProductCategoryRead

product_categories_router = APIRouter(prefix="/product-categories", tags=["product-categories"])

@product_categories_router.get("", response_model=list[ProductCategoryRead])
async def product_categories_get(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    name: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: Literal["newest", "name_asc", "name_desc"] | None = Query(default="name_asc"),
    db: AsyncSession = Depends(get_db),
) -> list[ProductCategoryRead]: return [ProductCategoryRead.model_validate(category) for category in await get_product_categories(db, q=q, name=name, offset=offset, limit=limit, sort=sort)]
