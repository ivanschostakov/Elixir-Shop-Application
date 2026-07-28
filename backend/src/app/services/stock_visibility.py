from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import CatalogSettings, Product


CATALOG_SETTINGS_ID = 1


@dataclass(frozen=True, slots=True)
class StockVisibilityPolicy:
    enabled: bool = False
    global_reduction: int = 0

    def reduction_for(self, product: Product | None) -> int:
        if not self.enabled:
            return 0
        override = getattr(product, "stock_reduction_override", None)
        if override is not None:
            return max(0, int(override))
        return max(0, int(self.global_reduction))

    def visible_stock(self, stock: int | None, product: Product | None) -> int:
        return max(0, int(stock or 0) - self.reduction_for(product))


async def get_stock_visibility_policy(db: AsyncSession) -> StockVisibilityPolicy:
    settings = await db.get(CatalogSettings, CATALOG_SETTINGS_ID)
    if settings is None:
        return StockVisibilityPolicy()
    return StockVisibilityPolicy(
        enabled=bool(settings.stock_reduction_enabled),
        global_reduction=max(0, int(settings.stock_reduction or 0)),
    )
