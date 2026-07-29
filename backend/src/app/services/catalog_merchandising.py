from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import CatalogSettings, Product

CATALOG_SETTINGS_ID = 1
DEFAULT_NEW_PRODUCT_DAYS = 30
MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CatalogMerchandisingPolicy:
    new_product_days: int = DEFAULT_NEW_PRODUCT_DAYS


async def get_catalog_merchandising_policy(db: AsyncSession) -> CatalogMerchandisingPolicy:
    settings = await db.get(CatalogSettings, CATALOG_SETTINGS_ID)
    return CatalogMerchandisingPolicy(
        new_product_days=settings.new_product_days if settings is not None else DEFAULT_NEW_PRODUCT_DAYS,
    )


def new_product_cutoff(
    policy: CatalogMerchandisingPolicy,
    *,
    now: datetime | None = None,
) -> datetime:
    return (now or ufa_now()) - timedelta(days=policy.new_product_days)


def product_is_new(
    product: Product,
    policy: CatalogMerchandisingPolicy,
    *,
    now: datetime | None = None,
) -> bool:
    if product.is_new_manual:
        return True
    if policy.new_product_days <= 0:
        return False
    return product.created_at >= new_product_cutoff(policy, now=now)


def normalize_percent(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return max(
        Decimal("0.00"),
        min(Decimal("100.00"), Decimal(str(value)).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)),
    )


def product_catalog_discount_percent(product: Product | None) -> Decimal:
    if product is None:
        return Decimal("0.00")
    percentages = [normalize_percent(getattr(product, "discount_percent", None))]
    for link in getattr(product, "products_by_category", ()) or ():
        category = getattr(link, "category", None)
        if category is not None and not category.archived:
            percentages.append(normalize_percent(category.discount_percent))
    return max(percentages, default=Decimal("0.00"))


def apply_percent_discount(
    price: Decimal | int | float | str,
    percent: Decimal | int | float | str | None,
) -> Decimal:
    original = Decimal(str(price)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    normalized_percent = normalize_percent(percent)
    if normalized_percent <= Decimal("0.00"):
        return original
    discounted = original - ((original * normalized_percent) / Decimal("100.00"))
    return max(Decimal("0.00"), discounted.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def catalog_unit_price(price: Decimal, product: Product | None) -> Decimal:
    return apply_percent_discount(price, product_catalog_discount_percent(product))
