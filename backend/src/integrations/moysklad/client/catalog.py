import asyncio
from src.integrations.moysklad.rows import build_variant_rows, build_product_rows, EXCLUDED_PATHS
from src.integrations.moysklad.schemas import MoySkladCatalogSyncStats, MoySkladInitialRelinkStats
from src.normalize import coerce_uuid
from .common import logger


class CatalogMixin:
    async def fetch_catalog_rows(self):
        logger.info("MoySklad catalog fetch started")
        products, variants, stocks = await asyncio.gather(self.get_all("/entity/product"), self.get_all("/entity/variant", expand="product"), self.get_all("/report/stock/all"),)

        products = [product for product in products if (product.get("pathName") not in EXCLUDED_PATHS or coerce_uuid(product.get("id")) in self._included_product_ids)]
        stats = MoySkladCatalogSyncStats()
        product_rows, products_by_code, products_by_id = build_product_rows(products, stats)
        variant_rows = build_variant_rows(variants, stocks, products_by_code, products_by_id, stats)
        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        logger.info("MoySklad catalog rows prepared products=%s variants=%s", stats.fetched_products, stats.fetched_variants)
        return product_rows, variant_rows, stats


    async def initial_relink_system_ids(self, _session, *, dry_run: bool = False) -> MoySkladInitialRelinkStats:
        logger.warning("MoySklad initial relink is not implemented in the modular client; returning empty stats.")
        return MoySkladInitialRelinkStats(dry_run=dry_run)
