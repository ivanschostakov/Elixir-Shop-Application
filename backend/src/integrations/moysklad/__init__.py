__all__ = [
    "MoySkladCatalogSyncStats",
    "MoySkladClient",
    "MoySkladInitialRelinkStats",
    "MoySkladProductRow",
    "MoySkladVariantRow",
    "get_moysklad_catalog_client",
    "moysklad_catalog_client",
    "run_moysklad_initial_relink",
    "sync_moysklad_product_catalog",
    "upsert_moysklad_catalog_rows",
]

from .client import (
    MoySkladCatalogSyncStats,
    MoySkladClient,
    MoySkladInitialRelinkStats,
    MoySkladProductRow,
    MoySkladVariantRow,
    moysklad_catalog_client,
    run_moysklad_initial_relink,
    sync_moysklad_product_catalog,
    upsert_moysklad_catalog_rows,
)


def get_moysklad_catalog_client() -> MoySkladClient: return moysklad_catalog_client
