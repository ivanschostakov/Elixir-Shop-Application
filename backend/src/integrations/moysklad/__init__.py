from .client import MoySkladClient, get_moysklad_client
from .order_sync import sync_order_to_moysklad, sync_order_to_moysklad_safe
from .sync import (
    run_moysklad_initial_relink,
    sync_moysklad_product_catalog,
    upsert_catalog_rows,
)


def get_moysklad_catalog_client() -> MoySkladClient:
    return get_moysklad_client()


__all__ = [
    "MoySkladClient",
    "get_moysklad_catalog_client",
    "get_moysklad_client",
    "run_moysklad_initial_relink",
    "sync_order_to_moysklad",
    "sync_order_to_moysklad_safe",
    "sync_moysklad_product_catalog",
    "upsert_catalog_rows",
]
