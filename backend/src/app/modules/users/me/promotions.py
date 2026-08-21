from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.products.helpers import product_image_url
from src.database import get_db
from src.database.models import Product, ProductByCategory, ProductCategory, User

from .schemas.promotions import ProfilePromotionRead

my_promotions_router = APIRouter(prefix="/promotions", tags=["my_promotions"])


def _representative_product(category: ProductCategory) -> Product | None:
    products = [
        link.product
        for link in category.products_by_category
        if link.product is not None and not link.product.archived
    ]
    if not products:
        return None
    return min(
        products,
        key=lambda product: (
            not product.has_image,
            not product.in_stock,
            -product.priority,
            product.id,
        ),
    )


@my_promotions_router.get("", response_model=list[ProfilePromotionRead])
async def list_my_promotions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[ProfilePromotionRead]:
    products = list(
        (
            await db.execute(
                select(Product)
                .where(
                    Product.archived.is_(False),
                    Product.discount_percent > Decimal("0.00"),
                )
                .order_by(
                    Product.discount_percent.desc(),
                    Product.priority.desc(),
                    Product.updated_at.desc(),
                    Product.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    categories = list(
        (
            await db.execute(
                select(ProductCategory)
                .options(
                    selectinload(ProductCategory.products_by_category).selectinload(
                        ProductByCategory.product
                    )
                )
                .where(
                    ProductCategory.archived.is_(False),
                    ProductCategory.is_visible_in_app.is_(True),
                    ProductCategory.discount_percent > Decimal("0.00"),
                )
                .order_by(
                    ProductCategory.discount_percent.desc(),
                    ProductCategory.updated_at.desc(),
                    ProductCategory.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )

    result = [
        ProfilePromotionRead(
            kind="product",
            title=product.name,
            subtitle="Специальная скидка на товар",
            discount_percent=product.discount_percent,
            image_url=product_image_url(request, product),
            product_id=product.id,
            product_name=product.name,
        )
        for product in products
    ]
    for category in categories:
        representative = _representative_product(category)
        if representative is None:
            continue
        result.append(
            ProfilePromotionRead(
                kind="category",
                title=category.name,
                subtitle=f"Скидка на всю категорию · {representative.name}",
                discount_percent=category.discount_percent,
                image_url=product_image_url(request, representative),
                product_id=representative.id,
                product_name=representative.name,
                category_id=category.id,
                category_name=category.name,
            )
        )

    return sorted(
        result,
        key=lambda promotion: (
            -promotion.discount_percent,
            0 if promotion.kind == "product" else 1,
            promotion.title.casefold(),
        ),
    )
