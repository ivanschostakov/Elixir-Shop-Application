from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.crud import get_variant_by_id
from src.database.models import StockNotificationSubscription, User
from src.database.schemas import (
    StockNotificationSubscriptionDeleteResponse,
    StockNotificationSubscriptionRead,
    StockNotificationSubscriptionUpsert,
)

stock_subscriptions_router = APIRouter(prefix="/stock-subscriptions", tags=["stock-subscriptions"])


@stock_subscriptions_router.post("", response_model=StockNotificationSubscriptionRead, status_code=status.HTTP_200_OK)
async def upsert_my_stock_subscription(
    payload: StockNotificationSubscriptionUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StockNotificationSubscriptionRead:
    variant = await get_variant_by_id(db, payload.variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    existing = (
        await db.execute(
            select(StockNotificationSubscription).where(
                StockNotificationSubscription.user_id == current_user.id,
                StockNotificationSubscription.variant_id == payload.variant_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = StockNotificationSubscription(
            user_id=current_user.id,
            variant_id=payload.variant_id,
            is_active=True,
            notified_at=None,
        )
        db.add(existing)
    else:
        existing.is_active = True
        existing.notified_at = None

    await db.commit()
    await db.refresh(existing)
    return StockNotificationSubscriptionRead.model_validate(existing)


@stock_subscriptions_router.delete(
    "/{variant_id}",
    response_model=StockNotificationSubscriptionDeleteResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_my_stock_subscription(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StockNotificationSubscriptionDeleteResponse:
    existing = (
        await db.execute(
            select(StockNotificationSubscription).where(
                StockNotificationSubscription.user_id == current_user.id,
                StockNotificationSubscription.variant_id == variant_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return StockNotificationSubscriptionDeleteResponse(ok=True)

    existing.is_active = False
    await db.commit()
    return StockNotificationSubscriptionDeleteResponse(ok=True)
