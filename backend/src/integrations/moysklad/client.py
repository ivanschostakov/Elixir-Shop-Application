import asyncio
import logging
import re
import shutil
import time
import uuid

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    MOY_SKLAD_BASE_URL,
    MOY_SKLAD_STOCK_RESERVE,
    MOY_SKLAD_TOKEN,
    MOY_SKLAD_TIMEOUT_SECONDS,
    PRODUCTS_MEDIA_DIR,
    ufa_now,
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
from src.product_media import product_image_path, variant_image_path
from src.normalize import coerce_decimal, coerce_uuid, fit_text, optional_str

from .schemas import (
    MoySkladCatalogSyncStats,
    MoySkladInitialRelinkStats,
    MoySkladProductRow,
    MoySkladVariantRow,
)

logger = logging.getLogger(__name__)


class MoySkladInitialRelinkError(RuntimeError):
    pass


_MATCH_TOKEN_RE = re.compile(r"[^0-9a-zа-яё]+", re.IGNORECASE)


def _normalized_match_text(value: Any) -> str | None:
    normalized = optional_str(value)
    if normalized is None:
        return None
    normalized = normalized.casefold().replace("ё", "е")
    normalized = _MATCH_TOKEN_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _without_prefix(value: str | None, prefix: str | None) -> str | None:
    if not value or not prefix:
        return value
    if value == prefix:
        return value
    if value.startswith(f"{prefix} "):
        return value[len(prefix) + 1 :].strip() or value
    return value


def _match_keys_from_text(value: Any, *, product_name: Any = None) -> set[str]:
    key = _normalized_match_text(value)
    if key is None:
        return set()
    product_key = _normalized_match_text(product_name)
    keys = {key}
    stripped = _without_prefix(key, product_key)
    if stripped:
        keys.add(stripped)
    return keys


def _variant_characteristic_keys(variant: dict[str, Any]) -> set[str]:
    characteristics = variant.get("characteristics")
    if not isinstance(characteristics, list):
        return set()

    values: list[str] = []
    named_values: list[str] = []
    for item in characteristics:
        if not isinstance(item, dict):
            continue
        name = _normalized_match_text(item.get("name"))
        value = _normalized_match_text(item.get("value"))
        if value:
            values.append(value)
        if name and value:
            named_values.append(f"{name} {value}")
        elif name:
            named_values.append(name)

    keys: set[str] = set()
    if values:
        keys.add(" ".join(values))
        keys.add(" ".join(sorted(values)))
    if named_values:
        keys.add(" ".join(named_values))
        keys.add(" ".join(sorted(named_values)))
    return {key for key in keys if key}


def _moysklad_variant_match_keys(variant: dict[str, Any], *, product_name: Any = None) -> set[str]:
    keys = _match_keys_from_text(variant.get("name"), product_name=product_name)
    keys.update(_variant_characteristic_keys(variant))
    return keys


def _local_variant_match_keys(variant: Variant, *, product_name: Any = None) -> set[str]:
    keys = _match_keys_from_text(variant.name, product_name=product_name)
    sku_key = _normalized_match_text(variant.sku)
    if sku_key:
        keys.add(sku_key)
    return keys


def _stock_assortment_id(stock: dict[str, Any]) -> uuid.UUID | None:
    direct = coerce_uuid(stock.get("assortmentId"))
    if direct is not None:
        return direct

    assortment = stock.get("assortment")
    if isinstance(assortment, dict):
        assortment_id = coerce_uuid(assortment.get("id"))
        if assortment_id is not None:
            return assortment_id
        meta = assortment.get("meta")
        if isinstance(meta, dict):
            href = optional_str(meta.get("href"))
            if href:
                return coerce_uuid(href.rstrip("/").rsplit("/", 1)[-1])

    meta = stock.get("meta")
    if isinstance(meta, dict):
        href = optional_str(meta.get("href"))
        if href:
            return coerce_uuid(href.rstrip("/").rsplit("/", 1)[-1])
    return None


def _image_report_item(kind: str, product_id: int, old_system_id: uuid.UUID, new_system_id: uuid.UUID, source: Path, target: Path, *, error: str | None = None) -> dict[str, str]:
    item = {
        "kind": kind,
        "product_id": str(product_id),
        "old_system_id": str(old_system_id),
        "new_system_id": str(new_system_id),
        "source": str(source),
        "target": str(target),
    }
    if error:
        item["error"] = error
    return item


def _rollback_image_renames(image_renames: list[dict[str, str]]) -> None:
    for item in reversed(image_renames):
        source = Path(item["source"])
        target = Path(item["target"])
        if not target.exists() or source.exists():
            continue
        target.rename(source)
        logger.warning("Rolled back MoySklad image rename target=%s source=%s", target, source)


class MoySkladClient:
    _EXCLUDED_PATH_FILTER = "pathName!=Товары интернет-магазинов/elixirpeptide.ru"
    _EXCLUDED_PATH_NAMES = {
        "Товары интернет-магазинов/elixirpeptide.ru",
        "Товары интернет-магазинов/https://elixirpeptide.ru/",
        "Пасхалка",
    }

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

    async def get_products(self) -> list[dict[str, Any]]:
        rows = await self._get_all_rows("/entity/product", base_params={"filter": self._EXCLUDED_PATH_FILTER})
        return [
            product
            for product in rows
            if optional_str(product.get("pathName")) not in self._EXCLUDED_PATH_NAMES
        ]
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
        product_rows, products_by_external_code, products_by_id = self._build_product_rows(products, stats)
        variant_rows = self._build_variant_rows(
            variants=variants,
            stocks=stocks,
            products_by_external_code=products_by_external_code,
            products_by_id=products_by_id,
            stats=stats,
        )

        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        self.log.info("MoySklad catalog rows prepared products=%s variants=%s", stats.fetched_products, stats.fetched_variants)
        return product_rows, variant_rows, stats

    @staticmethod
    def _build_product_rows(
        products: list[dict[str, Any]],
        stats: MoySkladCatalogSyncStats,
    ) -> tuple[list[MoySkladProductRow], dict[str, dict[str, Any]], dict[uuid.UUID, dict[str, Any]]]:
        rows: list[MoySkladProductRow] = []
        products_by_external_code: dict[str, dict[str, Any]] = {}
        products_by_id: dict[uuid.UUID, dict[str, Any]] = {}
        for product in products:
            product_id = coerce_uuid(product.get("id"))
            if product_id is None:
                stats.skipped_products_invalid_system_id += 1
                continue
            
            external_code = optional_str(product.get("externalCode"))
            if external_code and "#" in external_code:
                stats.skipped_products_variant_external_code += 1
                continue
            if external_code: products_by_external_code[external_code] = product
            products_by_id[product_id] = product

            sku_fallback = str(product_id)
            sku = fit_text(product.get("article") or product.get("code"), PRODUCT_SKU_MAX_LENGTH) or sku_fallback[:PRODUCT_SKU_MAX_LENGTH]
            name = fit_text(product.get("name"), PRODUCT_NAME_MAX_LENGTH) or sku[:PRODUCT_NAME_MAX_LENGTH]
            rows.append(MoySkladProductRow(
                system_id=product_id,
                sku=sku,
                name=name,
                description=normalize_product_text(product.get("description")),
                archived=False,
            ))
        
        return rows, products_by_external_code, products_by_id

    def _build_variant_rows(
        self,
        *,
        variants: list[dict[str, Any]],
        stocks: list[dict[str, Any]],
        products_by_external_code: dict[str, dict[str, Any]],
        products_by_id: dict[uuid.UUID, dict[str, Any]],
        stats: MoySkladCatalogSyncStats,
    ) -> list[MoySkladVariantRow]:
        stock_by_external_code: dict[str, dict[str, Any]] = {}
        duplicated_stock_external_codes: set[str] = set()
        stock_by_assortment_id: dict[uuid.UUID, dict[str, Any]] = {}
        for stock in stocks:
            assortment_id = _stock_assortment_id(stock)
            if assortment_id is not None:
                stock_by_assortment_id[assortment_id] = stock

            external_code = optional_str(stock.get("externalCode"))
            if external_code:
                if external_code in stock_by_external_code:
                    duplicated_stock_external_codes.add(external_code)
                stock_by_external_code[external_code] = stock

        for external_code in duplicated_stock_external_codes:
            stock_by_external_code.pop(external_code, None)

        rows: list[MoySkladVariantRow] = []
        variants_seen_by_product_id: set[uuid.UUID] = set()

        for variant in variants:
            variant_id = coerce_uuid(variant.get("id"))
            if variant_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            variant_external_code = optional_str(variant.get("externalCode"))
            product_meta = variant.get("product") if isinstance(variant.get("product"), dict) else {}
            product_system_id = coerce_uuid(product_meta.get("id"))
            product = products_by_id.get(product_system_id) if product_system_id is not None else None
            product_external_code = optional_str(product_meta.get("externalCode")) or variant_external_code
            if product is None and product_external_code is not None:
                product = products_by_external_code.get(product_external_code)
                product_system_id = coerce_uuid(product.get("id")) if product is not None else None
            if product is None:
                stats.skipped_variants_missing_product += 1
                continue

            if product_system_id is None:
                stats.skipped_variants_invalid_system_id += 1
                continue

            variants_seen_by_product_id.add(product_system_id)
            stock = stock_by_assortment_id.get(variant_id) or stock_by_external_code.get(variant_external_code or "")
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

            stock = stock_by_assortment_id.get(product_system_id) or stock_by_external_code.get(product_external_code)
            rows.append(MoySkladVariantRow(
                system_id=self.synthetic_variant_system_id(product_system_id),
                product_system_id=product_system_id,
                sku=fit_text(product.get("code"), VARIANT_SKU_MAX_LENGTH),
                name="Основной вариант",
                stock=self._available_stock((stock or {}).get("quantity")),
                price=self._sale_price(product),
            ))

        return rows

    def _backup_product_images(self, stats: MoySkladInitialRelinkStats) -> None:
        backup_root = PRODUCTS_MEDIA_DIR.parent / "product-image-backups"
        timestamp = ufa_now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_root / f"moysklad-initial-relink-{timestamp}"
        suffix = 1
        while backup_path.exists():
            suffix += 1
            backup_path = backup_root / f"moysklad-initial-relink-{timestamp}-{suffix}"

        backup_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PRODUCTS_MEDIA_DIR, backup_path)
        stats.image_backup_path = str(backup_path)
        logger.info("MoySklad initial relink backed up product images source=%s backup=%s", PRODUCTS_MEDIA_DIR, backup_path)

    @staticmethod
    def _variant_parent_external_code(variant: dict[str, Any]) -> uuid.UUID | None:
        product_meta = variant.get("product") if isinstance(variant.get("product"), dict) else {}
        return coerce_uuid(variant.get("externalCode")) or coerce_uuid(product_meta.get("externalCode"))

    def _add_image_rename_plan(
        self,
        plans: list[tuple[Path, Path, dict[str, str]]],
        *,
        stats: MoySkladInitialRelinkStats,
        kind: str,
        product_id: int,
        old_system_id: uuid.UUID,
        new_system_id: uuid.UUID,
        source: Path | None,
        target: Path | None,
    ) -> None:
        if old_system_id == new_system_id:
            return
        if source is None or target is None:
            return

        item = _image_report_item(kind, product_id, old_system_id, new_system_id, source, target)
        if not source.exists():
            stats.images_missing += 1
            stats.images_missing_report.append(item)
            logger.warning(
                "MoySklad initial relink image missing kind=%s product_id=%s old_system_id=%s source=%s",
                kind,
                product_id,
                old_system_id,
                source,
            )
            return

        if target.exists():
            stats.image_rename_failures += 1
            failure = {**item, "error": "target_exists"}
            stats.image_rename_failures_report.append(failure)
            raise MoySkladInitialRelinkError(f"Image rename target already exists: {target}")

        plans.append((source, target, item))

    def _execute_image_rename_plans(
        self,
        plans: list[tuple[Path, Path, dict[str, str]]],
        *,
        stats: MoySkladInitialRelinkStats,
    ) -> None:
        seen_targets: set[Path] = set()
        for _, target, item in plans:
            if target in seen_targets:
                stats.image_rename_failures += 1
                failure = {**item, "error": "duplicate_target"}
                stats.image_rename_failures_report.append(failure)
                raise MoySkladInitialRelinkError(f"Duplicate image rename target: {target}")
            seen_targets.add(target)

        stats.images_planned_for_rename = len(plans)
        if stats.dry_run:
            stats.image_renames.extend(item for _, _, item in plans)
            return

        for source, target, item in plans:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                source.rename(target)
            except Exception as exc:
                stats.image_rename_failures += 1
                failure = {**item, "error": str(exc)}
                stats.image_rename_failures_report.append(failure)
                _rollback_image_renames(stats.image_renames)
                raise MoySkladInitialRelinkError(f"Failed to rename image {source} -> {target}") from exc

            stats.images_renamed += 1
            stats.image_renames.append(item)
            logger.info("MoySklad initial relink image renamed source=%s target=%s", source, target)

    def _match_variants_for_product(
        self,
        *,
        local_product: Product,
        local_variants: list[Variant],
        moy_variants: list[dict[str, Any]],
        variants_by_system_id: dict[uuid.UUID, Variant],
        stats: MoySkladInitialRelinkStats,
    ) -> list[tuple[Variant, uuid.UUID, uuid.UUID, dict[str, Any]]]:
        valid_moy_variants: dict[uuid.UUID, dict[str, Any]] = {}
        for moy_variant in moy_variants:
            new_system_id = coerce_uuid(moy_variant.get("id"))
            if new_system_id is None:
                stats.skipped_variants_invalid_system_id += 1
                logger.warning("MoySklad initial relink skipped variant with invalid id payload=%s", moy_variant)
                continue

            conflict = variants_by_system_id.get(new_system_id)
            if conflict is not None and conflict.product_id != local_product.id:
                stats.skipped_variants_conflict_system_id += 1
                logger.warning(
                    "MoySklad initial relink skipped variant system_id conflict new_system_id=%s conflict_variant_id=%s product_id=%s",
                    new_system_id,
                    conflict.id,
                    local_product.id,
                )
                continue

            valid_moy_variants[new_system_id] = moy_variant

        local_index: dict[str, list[Variant]] = defaultdict(list)
        moy_index: dict[str, list[uuid.UUID]] = defaultdict(list)

        for local_variant in local_variants:
            for key in _local_variant_match_keys(local_variant, product_name=local_product.name):
                local_index[key].append(local_variant)

        for new_system_id, moy_variant in valid_moy_variants.items():
            for key in _moysklad_variant_match_keys(moy_variant, product_name=local_product.name):
                moy_index[key].append(new_system_id)

        matches: list[tuple[Variant, uuid.UUID, uuid.UUID, dict[str, Any]]] = []
        matched_local_ids: set[int] = set()
        matched_moy_ids: set[uuid.UUID] = set()

        for local_variant in local_variants:
            keys = _local_variant_match_keys(local_variant, product_name=local_product.name)
            candidate_ids: set[uuid.UUID] = set()
            ambiguous_key_seen = False
            for key in keys:
                local_bucket = local_index.get(key, [])
                moy_bucket = moy_index.get(key, [])
                if len(local_bucket) == 1 and len(moy_bucket) == 1:
                    candidate_ids.add(moy_bucket[0])
                elif local_bucket and moy_bucket:
                    ambiguous_key_seen = True

            if len(candidate_ids) == 1:
                new_system_id = next(iter(candidate_ids))
                if new_system_id in matched_moy_ids:
                    stats.skipped_variants_ambiguous += 1
                    logger.warning(
                        "MoySklad initial relink skipped ambiguous variant match local_variant_id=%s new_system_id=%s",
                        local_variant.id,
                        new_system_id,
                    )
                    continue

                conflict = variants_by_system_id.get(new_system_id)
                if conflict is not None and conflict.id != local_variant.id:
                    stats.skipped_variants_conflict_system_id += 1
                    logger.warning(
                        "MoySklad initial relink skipped variant system_id conflict local_variant_id=%s conflict_variant_id=%s new_system_id=%s",
                        local_variant.id,
                        conflict.id,
                        new_system_id,
                    )
                    continue

                matches.append((local_variant, local_variant.system_id, new_system_id, valid_moy_variants[new_system_id]))
                matched_local_ids.add(local_variant.id)
                matched_moy_ids.add(new_system_id)
                continue

            if len(candidate_ids) > 1 or ambiguous_key_seen:
                stats.skipped_variants_ambiguous += 1
                logger.warning(
                    "MoySklad initial relink skipped ambiguous variant local_variant_id=%s product_id=%s keys=%s candidates=%s",
                    local_variant.id,
                    local_product.id,
                    sorted(keys),
                    [str(candidate_id) for candidate_id in sorted(candidate_ids, key=str)],
                )

        for new_system_id, moy_variant in valid_moy_variants.items():
            if new_system_id in matched_moy_ids:
                continue
            stats.skipped_variants_missing_local += 1
            logger.warning(
                "MoySklad initial relink skipped MoySklad variant without deterministic local match product_id=%s new_system_id=%s name=%s",
                local_product.id,
                new_system_id,
                moy_variant.get("name"),
            )

        for local_variant, old_system_id, new_system_id, _ in matches:
            if old_system_id == new_system_id:
                stats.already_relinked_variants += 1
            else:
                stats.relinked_variants += 1
            logger.info(
                "MoySklad initial relink matched variant local_variant_id=%s product_id=%s old_system_id=%s new_system_id=%s",
                local_variant.id,
                local_variant.product_id,
                old_system_id,
                new_system_id,
            )

        return matches

    async def initial_relink_system_ids(self, session: AsyncSession, *, dry_run: bool = False) -> MoySkladInitialRelinkStats:
        products, variants = await asyncio.gather(self.get_products(), self.get_variants())
        stats = MoySkladInitialRelinkStats(dry_run=dry_run, fetched_products=len(products), fetched_variants=len(variants))

        local_products = list((await session.execute(select(Product))).scalars().all())
        local_variants = list((await session.execute(select(Variant))).scalars().all())
        products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
        variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}
        local_variants_by_product_id: dict[int, list[Variant]] = defaultdict(list)
        for variant in local_variants:
            local_variants_by_product_id[variant.product_id].append(variant)

        product_matches: list[tuple[Product, uuid.UUID, uuid.UUID, dict[str, Any]]] = []
        product_matches_by_old_system_id: dict[uuid.UUID, tuple[Product, uuid.UUID, uuid.UUID, dict[str, Any]]] = {}

        for moy_product in products:
            old_system_id = coerce_uuid(moy_product.get("externalCode"))
            if old_system_id is None:
                stats.skipped_products_invalid_external_code += 1
                logger.warning("MoySklad initial relink skipped product with invalid externalCode id=%s externalCode=%s", moy_product.get("id"), moy_product.get("externalCode"))
                continue

            new_system_id = coerce_uuid(moy_product.get("id"))
            if new_system_id is None:
                stats.skipped_products_invalid_system_id += 1
                logger.warning("MoySklad initial relink skipped product with invalid id externalCode=%s id=%s", moy_product.get("externalCode"), moy_product.get("id"))
                continue

            local_product = products_by_system_id.get(old_system_id)
            if local_product is None:
                local_product = products_by_system_id.get(new_system_id)
                if local_product is None:
                    stats.skipped_products_missing_local += 1
                    logger.warning(
                        "MoySklad initial relink skipped product without local match old_system_id=%s new_system_id=%s name=%s",
                        old_system_id,
                        new_system_id,
                        moy_product.get("name"),
                    )
                    continue

            conflict = products_by_system_id.get(new_system_id)
            if conflict is not None and conflict.id != local_product.id:
                stats.skipped_products_conflict_system_id += 1
                logger.warning(
                    "MoySklad initial relink skipped product system_id conflict old_system_id=%s new_system_id=%s local_product_id=%s conflict_product_id=%s",
                    old_system_id,
                    new_system_id,
                    local_product.id,
                    conflict.id,
                )
                continue

            if old_system_id in product_matches_by_old_system_id:
                stats.skipped_products_conflict_system_id += 1
                logger.warning(
                    "MoySklad initial relink skipped duplicate product externalCode old_system_id=%s new_system_id=%s",
                    old_system_id,
                    new_system_id,
                )
                continue

            product_match = (local_product, old_system_id, new_system_id, moy_product)
            product_matches.append(product_match)
            product_matches_by_old_system_id[old_system_id] = product_match
            stats.matched_products += 1
            if local_product.system_id == new_system_id:
                stats.already_relinked_products += 1
            else:
                stats.relinked_products += 1
            logger.info(
                "MoySklad initial relink matched product local_product_id=%s old_system_id=%s new_system_id=%s name=%s",
                local_product.id,
                old_system_id,
                new_system_id,
                local_product.name,
            )

        moy_variants_by_old_product_system_id: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
        for moy_variant in variants:
            old_product_system_id = self._variant_parent_external_code(moy_variant)
            if old_product_system_id is None:
                stats.skipped_variants_invalid_external_code += 1
                logger.warning("MoySklad initial relink skipped variant with invalid parent externalCode id=%s externalCode=%s", moy_variant.get("id"), moy_variant.get("externalCode"))
                continue
            if old_product_system_id not in product_matches_by_old_system_id:
                stats.skipped_variants_missing_parent_match += 1
                logger.warning(
                    "MoySklad initial relink skipped variant without matched parent old_product_system_id=%s id=%s name=%s",
                    old_product_system_id,
                    moy_variant.get("id"),
                    moy_variant.get("name"),
                )
                continue
            moy_variants_by_old_product_system_id[old_product_system_id].append(moy_variant)

        variant_matches: list[tuple[Variant, uuid.UUID, uuid.UUID, dict[str, Any]]] = []
        for local_product, old_system_id, _, _ in product_matches:
            product_variant_matches = self._match_variants_for_product(
                local_product=local_product,
                local_variants=local_variants_by_product_id.get(local_product.id, []),
                moy_variants=moy_variants_by_old_product_system_id.get(old_system_id, []),
                variants_by_system_id=variants_by_system_id,
                stats=stats,
            )
            stats.matched_variants += len(product_variant_matches)
            variant_matches.extend(product_variant_matches)

        image_plans: list[tuple[Path, Path, dict[str, str]]] = []
        for local_product, old_system_id, new_system_id, _ in product_matches:
            self._add_image_rename_plan(
                image_plans,
                stats=stats,
                kind="product",
                product_id=local_product.id,
                old_system_id=old_system_id,
                new_system_id=new_system_id,
                source=product_image_path(local_product.id, old_system_id),
                target=product_image_path(local_product.id, new_system_id),
            )

        for local_variant, old_system_id, new_system_id, _ in variant_matches:
            self._add_image_rename_plan(
                image_plans,
                stats=stats,
                kind="variant",
                product_id=local_variant.product_id,
                old_system_id=old_system_id,
                new_system_id=new_system_id,
                source=variant_image_path(local_variant.product_id, old_system_id),
                target=variant_image_path(local_variant.product_id, new_system_id),
            )

        if stats.dry_run:
            self._execute_image_rename_plans(image_plans, stats=stats)
            logger.info("MoySklad initial relink dry run completed stats=%s", stats.as_dict())
            return stats

        if product_matches or variant_matches or image_plans:
            self._backup_product_images(stats)

        self._execute_image_rename_plans(image_plans, stats=stats)

        try:
            for local_product, _, new_system_id, _ in product_matches:
                local_product.system_id = new_system_id

            for local_variant, _, new_system_id, moy_variant in variant_matches:
                local_variant.system_id = new_system_id
                new_name = fit_text(moy_variant.get("name"), VARIANT_NAME_MAX_LENGTH)
                if new_name:
                    local_variant.name = new_name

            await session.flush()
        except Exception:
            _rollback_image_renames(stats.image_renames)
            raise

        return stats


async def upsert_moysklad_catalog_rows(session: AsyncSession, products: list[MoySkladProductRow], variants: list[MoySkladVariantRow], stats: MoySkladCatalogSyncStats | None = None) -> MoySkladCatalogSyncStats:
    stats = stats or MoySkladCatalogSyncStats(fetched_products=len(products), fetched_variants=len(variants))
    logger.info("MoySklad catalog DB upsert started products=%s variants=%s", len(products), len(variants))

    local_products = list((await session.execute(select(Product))).scalars().all())
    local_variants = list((await session.execute(select(Variant))).scalars().all())
    products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
    products_by_sku = {product.sku: product for product in local_products}
    products_by_name = {product.name: product for product in local_products}
    variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}
    variants_by_product_id: dict[int, list[Variant]] = defaultdict(list)
    for variant in local_variants:
        variants_by_product_id[variant.product_id].append(variant)
    logger.info("MoySklad catalog DB local rows loaded products=%s variants=%s", len(local_products), len(local_variants))

    incoming_product_system_ids = {product.system_id for product in products}
    incoming_variant_system_ids = {variant.system_id for variant in variants}

    for product in products:
        payload = {"sku": product.sku, "name": product.name, "archived": product.archived}
        local_product = products_by_system_id.get(product.system_id)
        if local_product is None:
            sku_conflict = products_by_sku.get(product.sku)
            if sku_conflict is not None:
                stats.skipped_products_conflict_sku += 1
                logger.warning(
                    "MoySklad sync skipped product with conflicting sku system_id=%s sku=%s conflict_product_id=%s",
                    product.system_id,
                    product.sku,
                    sku_conflict.id,
                )
                continue

            name_conflict = products_by_name.get(product.name)
            if name_conflict is not None:
                stats.skipped_products_conflict_name += 1
                logger.warning(
                    "MoySklad sync skipped product with conflicting name system_id=%s name=%s conflict_product_id=%s",
                    product.system_id,
                    product.name,
                    name_conflict.id,
                )
                continue

            local_product = Product(system_id=product.system_id, priority=0, **payload)
            session.add(local_product)
            await session.flush()
            products_by_system_id[product.system_id] = local_product
            products_by_sku[local_product.sku] = local_product
            products_by_name[local_product.name] = local_product
            variants_by_product_id.setdefault(local_product.id, [])
            stats.created_products += 1
            if product.archived:
                stats.archived_products += 1
            else:
                stats.unarchived_products += 1
            continue

        was_archived = local_product.archived
        sku_conflict = products_by_sku.get(product.sku)
        if sku_conflict is not None and sku_conflict.id != local_product.id:
            payload.pop("sku", None)
            stats.skipped_products_conflict_sku += 1
            logger.warning(
                "MoySklad sync skipped sku update with conflict local_product_id=%s system_id=%s sku=%s conflict_product_id=%s",
                local_product.id,
                product.system_id,
                product.sku,
                sku_conflict.id,
            )

        name_conflict = products_by_name.get(product.name)
        if name_conflict is not None and name_conflict.id != local_product.id:
            payload.pop("name", None)
            stats.skipped_products_conflict_name += 1
            logger.warning(
                "MoySklad sync skipped name update with conflict local_product_id=%s system_id=%s name=%s conflict_product_id=%s",
                local_product.id,
                product.system_id,
                product.name,
                name_conflict.id,
            )

        if _apply_changes(local_product, payload):
            stats.updated_products += 1
            products_by_sku[local_product.sku] = local_product
            products_by_name[local_product.name] = local_product
        if product.archived and not was_archived:
            stats.archived_products += 1
        if not product.archived and was_archived:
            stats.unarchived_products += 1

    for local_product in local_products:
        if local_product.system_id in incoming_product_system_ids:
            continue
        if not local_product.archived:
            local_product.archived = True
            local_product.in_stock = False
            stats.archived_products += 1
            stats.updated_products += 1
            logger.info(
                "MoySklad sync archived missing product local_product_id=%s system_id=%s name=%s",
                local_product.id,
                local_product.system_id,
                local_product.name,
            )

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
            "archived": False,
            "price": variant.price, }

        local_variant = variants_by_system_id.get(variant.system_id)
        if local_variant is None:
            local_variant = Variant(system_id=variant.system_id, **payload)
            session.add(local_variant)
            variants_by_system_id[variant.system_id] = local_variant
            variants_by_product_id.setdefault(local_product.id, []).append(local_variant)
            stats.created_variants += 1
            stats.unarchived_variants += 1
            continue

        was_archived = local_variant.archived
        if _apply_changes(local_variant, payload): stats.updated_variants += 1
        if was_archived:
            stats.unarchived_variants += 1

    for local_variant in local_variants:
        if local_variant.system_id in incoming_variant_system_ids:
            continue
        if local_variant.stock != 0 or not local_variant.archived:
            local_variant.stock = 0
            if not local_variant.archived:
                stats.archived_variants += 1
            local_variant.archived = True
            stats.missing_variants_archived += 1
            stats.updated_variants += 1
            logger.info(
                "MoySklad sync archived missing variant variant_id=%s system_id=%s product_id=%s name=%s",
                local_variant.id,
                local_variant.system_id,
                local_variant.product_id,
                local_variant.name,
            )

    for local_product in products_by_system_id.values():
        product_variants = variants_by_product_id.get(local_product.id, [])
        in_stock = (
            local_product.system_id in incoming_product_system_ids
            and not local_product.archived
            and any(not variant.archived and variant.stock > 0 for variant in product_variants)
        )
        if local_product.in_stock != in_stock:
            local_product.in_stock = in_stock
            stats.updated_products += 1

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


async def run_moysklad_initial_relink(*, dry_run: bool = False) -> MoySkladInitialRelinkStats:
    logger.info("MoySklad initial relink started dry_run=%s", dry_run)
    stats: MoySkladInitialRelinkStats | None = None
    async with SessionLocal() as session:
        try:
            stats = await moysklad_catalog_client.initial_relink_system_ids(session, dry_run=dry_run)
            if dry_run:
                await session.rollback()
            else:
                await session.commit()
            cache = get_cache_service()
            await cache.bump_namespace("catalog")
            await cache.bump_namespace("product")
            logger.info("MoySklad initial relink completed stats=%s", stats.as_dict())
            return stats

        except Exception:
            await session.rollback()
            if stats is not None and stats.image_renames:
                _rollback_image_renames(stats.image_renames)
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
