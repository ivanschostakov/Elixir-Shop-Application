"""Account/guest catalog scope, independent of passwords and admin privileges."""
import re

import config
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.dependencies import get_optional_current_user
from src.app.services.platform_availability import is_ios_request
from src.app.services.catalog_access import CatalogScope, customer_category_scope
from src.database import get_db
from src.database.models import Product, ProductByCategory, User

def scoped_catalog_read(path: str, method: str) -> bool:
    """These reads enforce iOS and account policy in authenticated dependencies."""
    if config.CATALOG_ACCESSORY_CATEGORY_ID <= 0 or method != "GET":
        return False
    path = path.rstrip("/")
    return path in {"/api/v1/products", "/api/v1/product-categories", "/api/v1/banners"} or bool(
        re.fullmatch(r"/api/v1/products/\d+(?:/similar|/reviews(?:/eligibility)?|/questions)?", path)
    )


async def get_catalog_scope(
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
) -> CatalogScope:
    scope = customer_category_scope(current_user.id if current_user else None)
    if scope is not None:
        return scope
    if config.APPLE_DEV_MODE and is_ios_request(request.headers):
        return ()
    return None


async def require_visible_product(
    product_id: int,
    scope: CatalogScope = Depends(get_catalog_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    if scope is None:
        return
    visible = await db.scalar(select(Product.id).where(
        Product.id == product_id,
        Product.archived.is_(False),
        Product.products_by_category.any(ProductByCategory.category_id.in_(scope)),
    ))
    if visible is None:
        raise HTTPException(status_code=404, detail="Product not found")
