from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Basket, BasketItem


ABANDONED_BASKET_INACTIVITY = timedelta(hours=24)


async def count_abandoned_baskets(
    db: AsyncSession,
    *,
    start: datetime,
    end: datetime,
) -> int:
    """Count non-empty baskets inactive for 24 hours within a reporting period."""
    value = (
        await db.execute(
            select(func.count(func.distinct(Basket.id)))
            .join(BasketItem)
            .where(
                Basket.updated_at >= start,
                Basket.updated_at <= end - ABANDONED_BASKET_INACTIVITY,
            )
        )
    ).scalar_one()
    return int(value or 0)
