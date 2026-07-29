from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.services.notifications.core import (
    activate_stock_notifications_for_product,
    deactivate_stock_notifications_for_product,
    has_active_stock_notifications_for_product,
)
from src.app.services.stock_visibility import get_stock_visibility_policy
from src.database import get_db
from src.database.crud import get_product_by_id
from src.database.models import User
from src.database.schemas import ProductStockSubscriptionStatusRead


stock_subscriptions_router = APIRouter(
    prefix="/users/me/stock-subscriptions/products",
    tags=["stock-subscriptions"],
    dependencies=[Depends(get_current_user)],
)


async def _get_product_or_404(db: AsyncSession, product_id: int):
    product = await get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@stock_subscriptions_router.get(
    "/{product_id}",
    response_model=ProductStockSubscriptionStatusRead,
)
async def stock_subscription_status(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductStockSubscriptionStatusRead:
    await _get_product_or_404(db, product_id)
    is_subscribed = await has_active_stock_notifications_for_product(
        db,
        user_id=current_user.id,
        product_id=product_id,
    )
    return ProductStockSubscriptionStatusRead(
        product_id=product_id,
        is_subscribed=is_subscribed,
    )


@stock_subscriptions_router.post(
    "/{product_id}",
    response_model=ProductStockSubscriptionStatusRead,
    status_code=status.HTTP_201_CREATED,
)
async def stock_subscription_create(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductStockSubscriptionStatusRead:
    product = await _get_product_or_404(db, product_id)
    variants = [variant for variant in product.variants if not variant.archived]
    stock_policy = await get_stock_visibility_policy(db)

    if not variants:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This product has no variants available for stock notifications",
        )

    if any(stock_policy.visible_stock(variant.stock, product) > 0 for variant in variants):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock notifications are only available for unavailable products",
        )

    await activate_stock_notifications_for_product(
        db,
        user_id=current_user.id,
        product_id=product_id,
    )
    return ProductStockSubscriptionStatusRead(product_id=product_id, is_subscribed=True)


@stock_subscriptions_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stock_subscription_delete(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await _get_product_or_404(db, product_id)
    await deactivate_stock_notifications_for_product(
        db,
        user_id=current_user.id,
        product_id=product_id,
    )
