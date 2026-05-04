import asyncio
import logging
import time
import uuid

from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    MOY_SKLAD_BASE_URL,
    MOY_SKLAD_STOCK_RESERVE,
    MOY_SKLAD_TOKEN,
    MOY_SKLAD_TIMEOUT_SECONDS,
)
from src.app.services.cache import get_cache_service
from src.database import SessionLocal
from src.database.limits import (
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    VARIANT_NAME_MAX_LENGTH,
    VARIANT_SKU_MAX_LENGTH,
)
from src.database.models import Product, Variant
from src.database.product_text import normalize_product_text
from src.normalize import coerce_decimal, coerce_uuid, fit_text, optional_str

from .schemas import (
    MoySkladCatalogSyncStats,
    MoySkladInitialRelinkStats,
    MoySkladProductRow,
    MoySkladVariantRow,
)

logger = logging.getLogger(__name__)


class MoySkladClient:
    _EXCLUDED_PATH_FILTER = "pathName!=Товары интернет-магазинов/elixirpeptide.ru"

    def __init__(self, *, token: str | None = MOY_SKLAD_TOKEN, base_url: str | None = MOY_SKLAD_BASE_URL, timeout_seconds: int = MOY_SKLAD_TIMEOUT_SECONDS, stock_reserve: int = MOY_SKLAD_STOCK_RESERVE) -> None:
        self._token = optional_str(token) or ""
        self._base_url = optional_str(base_url) or ""
        self._timeout_seconds = max(int(timeout_seconds), 1)
        self._stock_reserve = max(int(stock_reserve), 0)
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self.log = logging.getLogger(self.__class__.__name__)

    def is_configured(self) -> bool:
        return bool(self._token and self._base_url)

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.is_configured(): raise RuntimeError("MoySklad integration is not configured")
        if self._client is not None and not self._client.is_closed: return self._client

        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=httpx.Timeout(self._timeout_seconds),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/json;charset=utf-8",
                        "Content-Type": "application/json;charset=utf-8",
                    },
                )
            return self._client

    async def aclose(self) -> None:
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed: await self._client.aclose()
            self._client = None

    @staticmethod
    def synthetic_variant_system_id(product_system_id: uuid.UUID) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"elixir-shop:moysklad:synthetic-variant:{product_system_id}")

    @staticmethod
    def _money(value: float | int | str | Decimal | None) -> Decimal:
        if value is None: return Decimal("0")
        return Decimal(str(value)) / Decimal("100")

    def _sale_price(self, item: dict[str, Any]) -> Decimal:
        sale_prices = item.get("salePrices")
        if not isinstance(sale_prices, list) or not sale_prices: return Decimal("0")
        first = sale_prices[0]
        if not isinstance(first, dict): return Decimal("0")
        return self._money(first.get("value"))

    def _available_stock(self, value: Any) -> int:
        raw = max(int(coerce_decimal(value) or Decimal("0")), 0)
        if self._stock_reserve <= 0: return raw
        return raw - self._stock_reserve if raw >= self._stock_reserve else 0

    async def _get_page(self, path: str, *, limit: int = 100, offset: int = 0, **params: Any) -> dict[str, Any]:
        request_params = dict(params)
        request_params["limit"] = limit
        request_params["offset"] = offset
        client = await self._get_client()
        response = await client.get(path, params=request_params)
        response.raise_for_status()
        return response.json()

    async def _get_all_rows(self, path: str, *, base_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = await self._get_page(path, limit=100, offset=offset, **(base_params or {}))
            batch = data.get("rows", [])
            if not isinstance(batch, list): break
            rows.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100: break
            offset += 100
        return rows

    async def get_products(self) -> list[dict[str, Any]]: return await self._get_all_rows("/entity/product", base_params={"filter": self._EXCLUDED_PATH_FILTER})
    async def get_variants(self) -> list[dict[str, Any]]: return await self._get_all_rows("/entity/variant", base_params={"expand": "product"})
    async def get_stocks_report(self) -> list[dict[str, Any]]: return await self._get_all_rows("/report/stock/all", base_params={})

    async def fetch_catalog_rows(self) -> tuple[list[MoySkladProductRow], list[MoySkladVariantRow], MoySkladCatalogSyncStats]:
        self.log.info("MoySklad catalog fetch started")
        products, variants, stocks = await asyncio.gather(
            self.get_products(),
            self.get_variants(),
            self.get_stocks_report(), )
        self.log.info("MoySklad catalog fetch completed products=%s variants=%s stocks=%s", len(products), len(variants), len(stocks))

        stats = MoySkladCatalogSyncStats()
        product_rows, products_by_external_code = self._build_product_rows(products, stats)
        variant_rows = self._build_variant_rows(variants=variants, stocks=stocks, products_by_external_code=products_by_external_code, stats=stats)

        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        self.log.info("MoySklad catalog rows prepared products=%s variants=%s", stats.fetched_products, stats.fetched_variants)
        return product_rows, variant_rows, stats

    @staticmethod
    def _build_product_rows(products: list[dict[str, Any]], stats: MoySkladCatalogSyncStats) -> tuple[list[MoySkladProductRow], dict[str, dict[str, Any]]]:
        rows: list[MoySkladProductRow] = []
        products_by_external_code: dict[str, dict[str, Any]] = {}
        for product in products:
            product_id = coerce_uuid(product.get("id"))
            if product_id is None:
                stats.skipped_products_invalid_system_id += 1
                continue
            
            external_code = optional_str(product.get("externalCode"))
            if external_code: products_by_external_code[external_code] = product

            sku_fallback = str(product_id)
            sku = fit_text(product.get("article") or product.get("code"), PRODUCT_SKU_MAX_LENGTH) or sku_fallback[:PRODUCT_SKU_MAX_LENGTH]
            name = fit_text(product.get("name"), PRODUCT_NAME_MAX_LENGTH) or sku[:PRODUCT_NAME_MAX_LENGTH]
            rows.append(MoySkladProductRow(system_id=product_id,sku=sku, name=name, description=normalize_product_text(product.get("description"))))
        
        return rows, products_by_external_code

    def _build_variant_rows(self, *, variants: list[dict[str, Any]], stocks: list[dict[str, Any]], products_by_external_code: dict[str, dict[str, Any]], stats: MoySkladCatalogSyncStats) -> list[MoySkladVariantRow]:
        stock_by_external_code: dict[str, dict[str, Any]] = {}
        for stock in stocks:
            external_code = optional_str(stock.get("externalCode"))
            if external_code: stock_by_external_code[external_code] = stock

        rows: list[MoySkladVariantRow] = []
        variants_seen_by_product_id: set[uuid.UUID] = set()

        for variant in variants:
            variant_id = coerce_uuid(variant.get("id"))
            if variant_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            variant_external_code = optional_str(variant.get("externalCode"))
            product_meta = variant.get("product") if isinstance(variant.get("product"), dict) else {}
            product_external_code = optional_str(product_meta.get("externalCode")) or variant_external_code
            if product_external_code is None:
                stats.skipped_variants_missing_product += 1
                continue

            product = products_by_external_code.get(product_external_code)
            if product is None:
                stats.skipped_variants_missing_product += 1
                continue

            product_system_id = coerce_uuid(product.get("id"))
            if product_system_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            variants_seen_by_product_id.add(product_system_id)
            stock = stock_by_external_code.get(variant_external_code or "")
            stock_quantity = self._available_stock((stock or {}).get("quantity"))

            sku = fit_text(variant.get("code"), VARIANT_SKU_MAX_LENGTH)
            name_fallback = sku or "Основной вариант"
            rows.append(MoySkladVariantRow(
                system_id=variant_id,
                product_system_id=product_system_id,
                sku=sku,
                name=fit_text(variant.get("name"), VARIANT_NAME_MAX_LENGTH) or name_fallback[:VARIANT_NAME_MAX_LENGTH],
                stock=stock_quantity,
                price=self._sale_price(variant),
            ))

        # Ensure each product has at least one variant.
        for product_external_code, product in products_by_external_code.items():
            product_system_id = coerce_uuid(product.get("id"))
            if product_system_id is None: continue
            if product_system_id in variants_seen_by_product_id: continue

            stock = stock_by_external_code.get(product_external_code)
            rows.append(MoySkladVariantRow(
                system_id=self.synthetic_variant_system_id(product_system_id),
                product_system_id=product_system_id,
                sku=fit_text(product.get("code"), VARIANT_SKU_MAX_LENGTH),
                name="Основной вариант",
                stock=self._available_stock((stock or {}).get("quantity")),
                price=self._sale_price(product),
            ))

        return rows

    async def initial_relink_system_ids(self, session: AsyncSession) -> MoySkladInitialRelinkStats:
        products, variants = await asyncio.gather(self.get_products(), self.get_variants())
        stats = MoySkladInitialRelinkStats(fetched_products=len(products), fetched_variants=len(variants))

        local_products = list((await session.execute(select(Product))).scalars().all())
        local_variants = list((await session.execute(select(Variant))).scalars().all())
        products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
        variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}

        for moy_product in products:
            old_system_id = coerce_uuid(moy_product.get("externalCode"))
            if old_system_id is None:
                stats.skipped_products_invalid_external_code += 1
                continue

            new_system_id = coerce_uuid(moy_product.get("id"))
            if new_system_id is None:
                stats.skipped_products_invalid_system_id += 1
                continue

            local_product = products_by_system_id.get(old_system_id)
            if local_product is None:
                stats.skipped_products_missing_local += 1
                continue

            conflict = products_by_system_id.get(new_system_id)
            if conflict is not None and conflict.id != local_product.id:
                stats.skipped_products_conflict_system_id += 1
                continue

            if local_product.system_id != new_system_id:
                del products_by_system_id[old_system_id]
                local_product.system_id = new_system_id
                products_by_system_id[new_system_id] = local_product
                stats.relinked_products += 1

        for moy_variant in variants:
            old_system_id = coerce_uuid(moy_variant.get("externalCode"))
            if old_system_id is None:
                stats.skipped_variants_invalid_external_code += 1
                continue

            new_system_id = coerce_uuid(moy_variant.get("id"))
            if new_system_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            local_variant = variants_by_system_id.get(old_system_id)
            if local_variant is None:
                stats.skipped_variants_missing_local += 1
                continue

            conflict = variants_by_system_id.get(new_system_id)
            if conflict is not None and conflict.id != local_variant.id:
                stats.skipped_variants_conflict_system_id += 1
                continue

            if local_variant.system_id != new_system_id:
                del variants_by_system_id[old_system_id]
                local_variant.system_id = new_system_id
                variants_by_system_id[new_system_id] = local_variant
                stats.relinked_variants += 1

        return stats


async def upsert_moysklad_catalog_rows(session: AsyncSession, products: list[MoySkladProductRow], variants: list[MoySkladVariantRow], stats: MoySkladCatalogSyncStats | None = None) -> MoySkladCatalogSyncStats:
    stats = stats or MoySkladCatalogSyncStats(fetched_products=len(products), fetched_variants=len(variants))
    logger.info("MoySklad catalog DB upsert started products=%s variants=%s", len(products), len(variants))

    local_products = list((await session.execute(select(Product))).scalars().all())
    local_variants = list((await session.execute(select(Variant))).scalars().all())
    products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
    variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}
    logger.info("MoySklad catalog DB local rows loaded products=%s variants=%s", len(local_products), len(local_variants))

    for product in products:
        payload = {"sku": product.sku, "name": product.name, "description": product.description}
        local_product = products_by_system_id.get(product.system_id)
        if local_product is None:
            local_product = Product(system_id=product.system_id, priority=0, **payload)
            session.add(local_product)
            await session.flush()
            products_by_system_id[product.system_id] = local_product
            stats.created_products += 1
            continue

        if _apply_changes(local_product, payload):
            stats.updated_products += 1

    await session.flush()

    for variant in variants:
        local_product = products_by_system_id.get(variant.product_system_id)
        if local_product is None:
            stats.skipped_variants_missing_product += 1
            continue

        payload = {
            "product_id": local_product.id,
            "sku": variant.sku,
            "name": variant.name,
            "stock": variant.stock,
            "price": variant.price, }

        local_variant = variants_by_system_id.get(variant.system_id)
        if local_variant is None:
            local_variant = Variant(system_id=variant.system_id, **payload)
            session.add(local_variant)
            variants_by_system_id[variant.system_id] = local_variant
            stats.created_variants += 1
            continue

        if _apply_changes(local_variant, payload): stats.updated_variants += 1

    logger.info("MoySklad catalog DB upsert prepared stats=%s", stats.as_dict())
    return stats


async def sync_moysklad_product_catalog() -> MoySkladCatalogSyncStats:
    started = time.perf_counter()
    logger.info("MoySklad catalog sync started")
    product_rows, variant_rows, stats = await moysklad_catalog_client.fetch_catalog_rows()
    logger.info("MoySklad catalog sync fetched rows products=%s variants=%s", len(product_rows), len(variant_rows))
    from src.app.services.notifications.core import process_restock_notifications

    async with SessionLocal() as session:
        try:
            stats = await upsert_moysklad_catalog_rows(session, product_rows, variant_rows, stats)
            await session.commit()
            cache = get_cache_service()
            await cache.bump_namespace("catalog")
            await cache.bump_namespace("product")
            logger.info("MoySklad catalog sync committed stats=%s seconds=%.2f", stats.as_dict(), time.perf_counter() - started)

        except Exception:
            await session.rollback()
            logger.exception("MoySklad catalog sync rolled back after %.2fs", time.perf_counter() - started)
            raise

        try:
            restock_sent = await process_restock_notifications(session)
            if restock_sent: logger.info("MoySklad sync immediate restock notifications sent=%s seconds=%.2f", restock_sent, time.perf_counter() - started)

        except Exception:
            await session.rollback()
            logger.exception("MoySklad sync immediate restock notification processing failed")

    return stats


async def run_moysklad_initial_relink() -> MoySkladInitialRelinkStats:
    logger.info("MoySklad initial relink started")
    async with SessionLocal() as session:
        try:
            stats = await moysklad_catalog_client.initial_relink_system_ids(session)
            await session.commit()
            cache = get_cache_service()
            await cache.bump_namespace("catalog")
            await cache.bump_namespace("product")
            logger.info("MoySklad initial relink committed stats=%s", stats.as_dict())
            return stats

        except Exception:
            await session.rollback()
            logger.exception("MoySklad initial relink rolled back")
            raise


def _apply_changes(model: Any, payload: dict[str, Any]) -> bool:
    changed = False
    for field, value in payload.items():
        if getattr(model, field) == value: continue
        setattr(model, field, value)
        changed = True

    return changed


moysklad_catalog_client = MoySkladClient()
