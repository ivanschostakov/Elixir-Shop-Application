"""Configured customer catalog visibility; None means the full catalog."""
import config

CatalogScope = tuple[int, ...] | None


def customer_category_scope(user_id: int | None) -> CatalogScope:
    if config.CATALOG_ACCESSORY_CATEGORY_ID <= 0:
        return None
    restricted = (
        config.CATALOG_GUEST_ACCESSORIES_ONLY if user_id is None
        else str(user_id) in config.CATALOG_ACCESSORY_ONLY_USER_IDS
    )
    return (config.CATALOG_ACCESSORY_CATEGORY_ID,) if restricted else None
