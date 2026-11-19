"""Account/guest catalog scope, independent of passwords and admin privileges."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.dependencies import get_optional_current_user
from src.app.services.catalog_access import CatalogScope
from src.database import get_db
from src.database.models import Product, ProductByCategory, User

async def get_catalog_scope(
    request: Request,
    current_user: User | None = Depends(get_optional_current_user),
) -> CatalogScope:
    return None


async def require_visible_product(
    product_id: int,
    scope: CatalogScope = Depends(get_catalog_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    statement = select(Product.id).where(
        Product.id == product_id,
        Product.archived.is_(False),
        Product.is_visible_in_app.is_(True),
    )
    if scope is not None:
        statement = statement.where(
            Product.products_by_category.any(ProductByCategory.category_id.in_(scope)),
        )
    visible = await db.scalar(statement)
    if visible is None:
        raise HTTPException(status_code=404, detail="Product not found")
