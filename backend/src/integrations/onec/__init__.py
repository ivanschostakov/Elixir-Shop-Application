__all__ = [
    "OneCCatalogClient",
    "OneCCatalogSyncStats",
    "OneCIntegrationError",
    "OneCProductRow",
    "OneCVariantRow",
    "get_onec_catalog_client",
    "onec_catalog_client",
    "sync_onec_product_catalog",
    "upsert_onec_catalog_rows",
]

from .client import (
    OneCCatalogClient,
    OneCCatalogSyncStats,
    OneCIntegrationError,
    OneCProductRow,
    OneCVariantRow,
    onec_catalog_client,
    sync_onec_product_catalog,
    upsert_onec_catalog_rows,
)


def get_onec_catalog_client() -> OneCCatalogClient:
    return onec_catalog_client
