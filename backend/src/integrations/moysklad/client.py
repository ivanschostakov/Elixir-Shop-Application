import asyncio
import logging
from typing import Any

import httpx

from .rows import build_variant_rows, build_product_rows, EXCLUDED_PATHS
from .schemas import MoySkladCatalogSyncStats, MoySkladInitialRelinkStats

from config import MOY_SKLAD_BASE_URL, MOY_SKLAD_TOKEN, MOY_SKLAD_TIMEOUT_SECONDS
from src.normalize import optional_str

logger = logging.getLogger(__name__)

class MoySkladClient:
    def __init__(self, token: str | None = MOY_SKLAD_TOKEN, base_url: str | None = MOY_SKLAD_BASE_URL, timeout: int = MOY_SKLAD_TIMEOUT_SECONDS) -> None:
        self._token = optional_str(token) or ""
        self._base_url = optional_str(base_url) or ""
        self._timeout = max(int(timeout), 1)
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool: return bool(self._token and self._base_url)

    async def client(self) -> httpx.AsyncClient:
        if not self.is_configured(): raise RuntimeError("MoySklad integration is not configured")
        if self._client and not self._client.is_closed: return self._client

        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=httpx.Timeout(self._timeout),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/json;charset=utf-8",
                        "Content-Type": "application/json;charset=utf-8",
                    },
                )
            return self._client

    async def get_page(self, path: str, *, limit: int = 100, offset: int = 0, **params: Any) -> dict[str, Any]:
        client = await self.client()
        response = await client.get(path, params={**params, "limit": limit, "offset": offset})
        response.raise_for_status()
        return response.json()

    async def get_all(self, path: str, **params: Any) -> list[dict[str, Any]]:
        rows, offset = [], 0
        while True:
            data = await self.get_page(path, offset=offset, **params)
            batch = data.get("rows", [])
            if not isinstance(batch, list): break
            rows.extend(row for row in batch if isinstance(row, dict))
            if len(batch) < 100: break
            offset += 100
        return rows

    async def fetch_catalog_rows(client: MoySkladClient):
        logger.info("MoySklad catalog fetch started")
        products, variants, stocks = await asyncio.gather(
            client.get_all("/entity/product", filter="pathName!=Товары интернет-магазинов/elixirpeptide.ru"),
            client.get_all("/entity/variant", expand="product"),
            client.get_all("/report/stock/all"),
        )

        products = [p for p in products if p.get("pathName") not in EXCLUDED_PATHS]
        stats = MoySkladCatalogSyncStats()
        product_rows, products_by_code, products_by_id = build_product_rows(products, stats)
        variant_rows = build_variant_rows(variants, stocks, products_by_code, products_by_id, stats)
        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        logger.info("MoySklad catalog rows prepared products=%s variants=%s", stats.fetched_products, stats.fetched_variants)
        return product_rows, variant_rows, stats

    async def initial_relink_system_ids(self, _session, *, dry_run: bool = False) -> MoySkladInitialRelinkStats:
        logger.warning(
            "MoySklad initial relink is not implemented in the modular client; returning empty stats."
        )
        return MoySkladInitialRelinkStats(dry_run=dry_run)

    async def aclose(self) -> None:
        async with self._lock:
            if self._client and not self._client.is_closed: await self._client.aclose()
            self._client = None


moysklad_client = MoySkladClient()
def get_moysklad_client() -> MoySkladClient: return moysklad_client
