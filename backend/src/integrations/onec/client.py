import asyncio
import logging
import time
import uuid
import xml.etree.ElementTree as ET
import httpx

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    ONEC_ENTERPRISE_LOGIN,
    ONEC_ENTERPRISE_PASSWORD,
    ONEC_ENTERPRISE_URL,
    ONEC_REQUEST_TIMEOUT_SECONDS,
    ONEC_STOCK_RESERVE,
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
from src.normalize import coerce_decimal, coerce_uuid, fit_text, lower_optional_str, optional_str

from . import endpoints
from .errors import OneCIntegrationError
from .keywords import EXPIRE_KEYWORDS, USE_KEYWORDS
from .schemas import OneCProductRow, OneCCatalogSyncStats, OneCVariantRow

logger = logging.getLogger(__name__)


class OneCCatalogClient:
    TG_NOT_SOLD_PROP_KEY = "87cfc3b4-defa-11f0-8b75-fa163eccf8af"
    PARENT_KEY = "63d865c8-5fad-11f0-818d-fa163eccf8af"
    EMPTY_FEATURE_KEY = "00000000-0000-0000-0000-000000000000"
    FORCE_INCLUDE_PRODUCT_IDS = {"b019df8a-5a25-11f0-9098-fa163e347889", "101972c4-5a26-11f0-9098-fa163e347889", "3c8fd1e6-dd66-11ef-86f7-fa163e347889", "4039be2e-5a25-11f0-9098-fa163e347889", "346dda8e-5a26-11f0-9098-fa163e347889", "06543a26-5a26-11f0-9098-fa163e347889", "5242d4fc-5a25-11f0-9098-fa163e347889"}
    NS = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata", "d": "http://schemas.microsoft.com/ado/2007/08/dataservices", "atom": "http://www.w3.org/2005/Atom"}

    def __init__(self, *, base_url: str | None = ONEC_ENTERPRISE_URL, username: str | None = ONEC_ENTERPRISE_LOGIN, password: str | None = ONEC_ENTERPRISE_PASSWORD, timeout_seconds: int = ONEC_REQUEST_TIMEOUT_SECONDS, stock_reserve: int = ONEC_STOCK_RESERVE) -> None:
        self._base_url = optional_str(base_url) or ""
        self._username = optional_str(username) or ""
        self._password = optional_str(password) or ""
        self._timeout_seconds = timeout_seconds
        self._stock_reserve = max(int(stock_reserve), 0)
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self.log = logging.getLogger(self.__class__.__name__)

    def is_configured(self) -> bool:
        return bool(self._base_url and self._username and self._password)

    async def _get_client(self) -> httpx.AsyncClient:
        if not self.is_configured(): raise OneCIntegrationError("1C integration is not configured")
        if self._client is not None and not self._client.is_closed: return self._client

        async with self._client_lock:
            if self._client is None or self._client.is_closed: self._client = httpx.AsyncClient(auth=(self._username, self._password), limits=httpx.Limits(max_connections=20, max_keepalive_connections=10), timeout=httpx.Timeout(self._timeout_seconds), )
            return self._client

    async def aclose(self) -> None:
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed: await self._client.aclose()
            self._client = None

    async def fetch_odata(self, endpoint: str) -> list[dict[str, Any]]:
        url = f"{self._base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        client = await self._get_client()
        last_error: Exception | None = None
        started = time.perf_counter()

        for attempt in range(1, 4):
            try:
                response = await client.get(url)
                response.raise_for_status()
                records = self.parse_odata_feed(response.content)
                self.log.info("Fetched 1C endpoint endpoint=%s status=%s records=%s attempt=%s seconds=%.2f", endpoint, response.status_code, len(records), attempt, time.perf_counter() - started)
                return records
            
            except (httpx.HTTPError, ET.ParseError) as exc:
                last_error = exc
                self.log.warning("1C fetch attempt failed endpoint=%s attempt=%s error=%s", endpoint, attempt, exc)
                await asyncio.sleep(3)

        raise OneCIntegrationError(f"Failed to fetch 1C endpoint {endpoint!r}") from last_error

    @classmethod
    def parse_odata_feed(cls, content: bytes | str) -> list[dict[str, Any]]:
        root = ET.fromstring(content)
        records: list[dict[str, Any]] = []

        for entry in root.findall("atom:entry", cls.NS):
            properties = entry.find("atom:content/m:properties", cls.NS)
            if properties is None: continue

            record: dict[str, Any] = {}
            for elem in properties:
                tag = cls._strip_namespace(elem.tag)
                if tag == "ДополнительныеРеквизиты":
                    record[tag] = [
                        {cls._strip_namespace(sub_elem.tag): sub_elem.text for sub_elem in extra}
                        for extra in elem.findall("d:element", cls.NS)
                    ]
                    continue
                record[tag] = elem.text
            records.append(record)

        return records

    @staticmethod
    def _strip_namespace(tag: str) -> str: return tag.split("}", 1)[1] if "}" in tag else tag

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        normalized = lower_optional_str(value)
        return normalized in {"true", "1", "yes", "y", "да", "истина"}

    @classmethod
    def _not_sold_in_tg(cls, extras: Any) -> bool:
        if not isinstance(extras, list): return False
        for item in extras:
            if not isinstance(item, dict): continue
            property_key = lower_optional_str(item.get("Свойство_Key"))
            if property_key == cls.TG_NOT_SOLD_PROP_KEY and cls._is_truthy(item.get("Значение")): return True

        return False

    @staticmethod
    def _extra_text_by_keywords(extras: Any, keywords: list[str]) -> str | None:
        if not isinstance(extras, list): return None
        normalized_keywords = [keyword.casefold() for keyword in keywords]
        for item in extras:
            if not isinstance(item, dict): continue
            text = optional_str(item.get("ТекстоваяСтрока"))
            if text and any(keyword in text.casefold() for keyword in normalized_keywords): return text
            
        return None

    @classmethod
    def _include_product(cls, record: dict[str, Any]) -> bool:
        ref_key = lower_optional_str(record.get("Ref_Key"))
        if not ref_key: return False
        if cls._is_truthy(record.get("Недействителен")) or cls._is_truthy(record.get("DeletionMark")): return False
        if optional_str(record.get("ТипНоменклатуры")) != "Запас": return False
        if ref_key not in cls.FORCE_INCLUDE_PRODUCT_IDS and lower_optional_str(record.get("Parent_Key")) != cls.PARENT_KEY: return False
        return not cls._not_sold_in_tg(record.get("ДополнительныеРеквизиты"))

    @classmethod
    def _parse_period(cls, value: Any) -> datetime | None:
        normalized = optional_str(value)
        if not normalized: return None
        try: parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError: return None
        if parsed.tzinfo is not None: return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def _available_stock(self, value: Any) -> int:
        balance = coerce_decimal(value) or Decimal("0")
        raw_stock = max(int(balance), 0)
        if self._stock_reserve <= 0: return raw_stock
        return raw_stock - self._stock_reserve if raw_stock >= self._stock_reserve else 0

    @staticmethod
    def synthetic_variant_system_id(product_system_id: uuid.UUID) -> uuid.UUID: return uuid.uuid5(uuid.NAMESPACE_URL, f"elixir-shop:onec:synthetic-variant:{product_system_id}")

    @staticmethod
    def _fit_required(value: Any, max_length: int, *, fallback: str) -> str: return fit_text(value, max_length) or fallback[:max_length]

    async def fetch_products_1c(self) -> dict[str, dict[str, Any]]:
        products = await self.fetch_odata(endpoints.PRODUCTS)
        out: dict[str, dict[str, Any]] = {}

        for product in products:
            if not self._include_product(product): continue
            ref_key = lower_optional_str(product.get("Ref_Key"))
            if not ref_key: continue
            extras = product.get("ДополнительныеРеквизиты") or []
            out[ref_key] = {"onec_id": ref_key, "sku": product.get("Code"), "name": product.get("Description"), "description": product.get("Комментарий"), "usage": self._extra_text_by_keywords(extras, USE_KEYWORDS), "expiration": self._extra_text_by_keywords(extras, EXPIRE_KEYWORDS), }

        self.log.info("1C products ready raw=%s filtered=%s", len(products), len(out))
        return out

    async def fetch_features_1c(self) -> dict[str, dict[str, Any]]:
        features_raw = await self.fetch_odata(endpoints.FEATURES)
        features: dict[str, dict[str, Any]] = {}

        for feature in features_raw:
            if self._is_truthy(feature.get("DeletionMark")): continue
            feature_id = lower_optional_str(feature.get("Ref_Key"))
            product_id = lower_optional_str(feature.get("Owner"))
            if not feature_id or not product_id: continue
            features[feature_id] = {"onec_id": feature_id, "product_onec_id": product_id, "name": feature.get("Description"), "sku": feature.get("Code"), }

        self.log.info("1C features ready raw=%s filtered=%s", len(features_raw), len(features))
        return features

    async def fetch_prices_1c(self) -> dict[str, dict[str, Any]]:
        prices = await self.fetch_odata(endpoints.PRICES)
        latest: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}

        for price in prices:
            product_id = lower_optional_str(price.get("Номенклатура_Key"))
            feature_id = lower_optional_str(price.get("Характеристика_Key")) or self.EMPTY_FEATURE_KEY
            period = self._parse_period(price.get("Period"))
            if not product_id or period is None: continue
            key = (product_id, feature_id)
            previous = latest.get(key)
            if previous is None or period > previous[0]: latest[key] = (period, price)

        result = {
            f"{product_id}_{feature_id}": {"product_onec_id": product_id, "feature_onec_id": feature_id, "price": row.get("Цена"), }
            for (product_id, feature_id), (_, row) in latest.items()
        }
        self.log.info("1C prices ready raw=%s latest=%s", len(prices), len(result))
        return result

    async def fetch_balances_1c(self) -> dict[str, dict[str, Any]]:
        balances = await self.fetch_odata(endpoints.BALANCES)
        aggregated: dict[tuple[str, str], Decimal] = {}

        for balance in balances:
            product_id = lower_optional_str(balance.get("Номенклатура_Key"))
            feature_id = lower_optional_str(balance.get("Характеристика_Key")) or self.EMPTY_FEATURE_KEY
            if not product_id: continue
            key = (product_id, feature_id)
            aggregated[key] = aggregated.get(key, Decimal("0")) + (coerce_decimal(balance.get("Количество")) or Decimal("0"))

        result = {
            f"{product_id}_{feature_id}": {"product_onec_id": product_id, "feature_onec_id": feature_id, "balance": quantity, }
            for (product_id, feature_id), quantity in aggregated.items()
        }
        self.log.info("1C balances ready raw=%s aggregated=%s", len(balances), len(result))
        return result

    async def fetch_catalog_rows(self) -> tuple[list[OneCProductRow], list[OneCVariantRow], OneCCatalogSyncStats]:
        self.log.info("1C catalog fetch started")
        products, features, prices_map, balances_map = await asyncio.gather(self.fetch_products_1c(), self.fetch_features_1c(), self.fetch_prices_1c(), self.fetch_balances_1c(), )
        self.log.info("1C catalog fetch completed products=%s features=%s prices=%s balances=%s", len(products), len(features), len(prices_map), len(balances_map), )

        stats = OneCCatalogSyncStats()
        product_rows = self._build_product_rows(products, stats)
        feature_rows = self._merge_feature_rows(products, features, prices_map, balances_map, stats)
        variant_rows = self._build_variant_rows(feature_rows, stats)
        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        self.log.info("1C catalog rows prepared products=%s variants=%s synthetic_variants=%s skipped_products_invalid_system_id=%s skipped_variants_invalid_system_id=%s", stats.fetched_products, stats.fetched_variants, stats.synthetic_variants, stats.skipped_products_invalid_system_id, stats.skipped_variants_invalid_system_id, )
        return product_rows, variant_rows, stats

    def _build_product_rows(self, products: dict[str, dict[str, Any]], stats: OneCCatalogSyncStats) -> list[OneCProductRow]:
        rows: list[OneCProductRow] = []
        for product in products.values():
            system_id = coerce_uuid(product.get("onec_id"))
            if system_id is None:
                stats.skipped_products_invalid_system_id += 1
                continue

            sku = self._fit_required(product.get("sku"), PRODUCT_SKU_MAX_LENGTH, fallback=str(system_id))
            name = self._fit_required(product.get("name"), PRODUCT_NAME_MAX_LENGTH, fallback=sku)
            rows.append(OneCProductRow(system_id=system_id, sku=sku, name=name, description=normalize_product_text(product.get("description")), usage=normalize_product_text(product.get("usage")), expiration=normalize_product_text(product.get("expiration"))))
        return rows

    def _merge_feature_rows(self, products: dict[str, dict[str, Any]], features: dict[str, dict[str, Any]], prices_map: dict[str, dict[str, Any]], balances_map: dict[str, dict[str, Any]], stats: OneCCatalogSyncStats) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for feature_id, feature in features.items():
            product_id = optional_str(feature.get("product_onec_id"))
            if product_id not in products: continue
            key = f"{product_id}_{feature_id}"
            merged[feature_id] = {**feature, "price": prices_map.get(key, {}).get("price", "0"), "balance": balances_map.get(key, {}).get("balance", "0"), "synthetic": False, }

        products_with_features = {optional_str(feature.get("product_onec_id")) for feature in merged.values()}
        for product_id in products:
            if product_id in products_with_features: continue
            key = f"{product_id}_{self.EMPTY_FEATURE_KEY}"
            price = prices_map.get(key, {}).get("price", "0")
            balance = balances_map.get(key, {}).get("balance", "0")
            if (coerce_decimal(price) or Decimal("0")) <= 0 and (coerce_decimal(balance) or Decimal("0")) <= 0: continue
            synthetic_id = f"{product_id}__synthetic"
            merged[synthetic_id] = {"onec_id": synthetic_id, "product_onec_id": product_id, "name": "Основной вариант", "sku": "__AUTO_DEFAULT__", "price": price, "balance": balance, "synthetic": True, }
            stats.synthetic_variants += 1

        return merged

    def _build_variant_rows(self, features: dict[str, dict[str, Any]], stats: OneCCatalogSyncStats) -> list[OneCVariantRow]:
        rows: list[OneCVariantRow] = []
        for feature in features.values():
            product_system_id = coerce_uuid(feature.get("product_onec_id"))
            if product_system_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            if feature.get("synthetic"): system_id = self.synthetic_variant_system_id(product_system_id)
            else:
                system_id = coerce_uuid(feature.get("onec_id"))
                if system_id is None:
                    stats.skipped_variants_invalid_system_id += 1
                    continue

            sku = fit_text(feature.get("sku"), VARIANT_SKU_MAX_LENGTH)
            name_fallback = sku or "Основной вариант"
            rows.append(OneCVariantRow(system_id=system_id, product_system_id=product_system_id, sku=sku, name=self._fit_required(feature.get("name"), VARIANT_NAME_MAX_LENGTH, fallback=name_fallback), stock=self._available_stock(feature.get("balance")), price=coerce_decimal(feature.get("price")) or Decimal("0")))

        return rows


async def upsert_onec_catalog_rows(session: AsyncSession, products: list[OneCProductRow], variants: list[OneCVariantRow], stats: OneCCatalogSyncStats | None = None) -> OneCCatalogSyncStats:
    stats = stats or OneCCatalogSyncStats(fetched_products=len(products), fetched_variants=len(variants))
    logger.info("1C catalog DB upsert started products=%s variants=%s", len(products), len(variants))
    local_products = list((await session.execute(select(Product))).scalars().all())
    local_variants = list((await session.execute(select(Variant))).scalars().all())
    products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
    variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}
    logger.info("1C catalog DB local rows loaded products=%s variants=%s", len(local_products), len(local_variants))

    for product in products:
        payload = {"sku": product.sku, "name": product.name, "description": product.description, "usage": product.usage, "expiration": product.expiration, }
        local_product = products_by_system_id.get(product.system_id)
        if local_product is None:
            local_product = Product(system_id=product.system_id, priority=0, **payload)
            session.add(local_product)
            await session.flush()
            products_by_system_id[product.system_id] = local_product
            stats.created_products += 1
            continue

        if _apply_changes(local_product, payload): stats.updated_products += 1

    await session.flush()

    for variant in variants:
        local_product = products_by_system_id.get(variant.product_system_id)
        if local_product is None:
            stats.skipped_variants_missing_product += 1
            continue

        payload = {"product_id": local_product.id, "sku": variant.sku, "name": variant.name, "stock": variant.stock, "price": variant.price}
        local_variant = variants_by_system_id.get(variant.system_id)
        if local_variant is None:
            local_variant = Variant(system_id=variant.system_id, **payload)
            session.add(local_variant)
            variants_by_system_id[variant.system_id] = local_variant
            stats.created_variants += 1
            continue

        if _apply_changes(local_variant, payload): stats.updated_variants += 1

    logger.info("1C catalog DB upsert prepared stats=%s", stats.as_dict())
    return stats


async def sync_onec_product_catalog() -> OneCCatalogSyncStats:
    started = time.perf_counter()
    logger.info("1C catalog sync started")
    product_rows, variant_rows, stats = await onec_catalog_client.fetch_catalog_rows()
    logger.info("1C catalog sync fetched rows products=%s variants=%s", len(product_rows), len(variant_rows))
    from src.app.services.notifications.core import process_restock_notifications

    async with SessionLocal() as session:
        try:
            stats = await upsert_onec_catalog_rows(session, product_rows, variant_rows, stats)
            await session.commit()
            cache = get_cache_service()
            await cache.bump_namespace("catalog")
            await cache.bump_namespace("product")
            logger.info("1C catalog sync committed stats=%s seconds=%.2f", stats.as_dict(), time.perf_counter() - started)

        except Exception:
            await session.rollback()
            logger.exception("1C catalog sync rolled back after %.2fs", time.perf_counter() - started)
            raise

        try:
            restock_sent = await process_restock_notifications(session)
            if restock_sent: logger.info("1C sync immediate restock notifications sent=%s seconds=%.2f", restock_sent, time.perf_counter() - started, )

        except Exception:
            await session.rollback()
            logger.exception("1C sync immediate restock notification processing failed")

    return stats


def _apply_changes(model: Any, payload: dict[str, Any]) -> bool:
    changed = False
    for field, value in payload.items():
        if getattr(model, field) == value: continue
        setattr(model, field, value)
        changed = True

    return changed


onec_catalog_client = OneCCatalogClient()
