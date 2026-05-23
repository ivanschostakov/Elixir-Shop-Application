from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from config import MOY_SKLAD_STOCK_RESERVE
from src.database.limits import PRODUCT_NAME_MAX_LENGTH, PRODUCT_SKU_MAX_LENGTH, VARIANT_NAME_MAX_LENGTH, VARIANT_SKU_MAX_LENGTH
from src.database.product_text import normalize_product_text
from src.normalize import coerce_uuid, fit_text, optional_str

from .utils import assortment_id, available_stock, display_variant_name, sale_price
from .schemas import MoySkladCatalogSyncStats, MoySkladProductRow, MoySkladVariantRow


EXCLUDED_PATHS = {
    "Товары интернет-магазинов/elixirpeptide.ru",
    "Товары интернет-магазинов/https://elixirpeptide.ru/",
    "Пасхалка",
}
EXCLUDED_NAME_PREFIXES = ("пакет",)
EXCLUDED_NAME_PARTS = ("сырье", "сырьё")


def synthetic_variant_id(product_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"elixir-shop:moysklad:synthetic-variant:{product_id}")


def is_excluded_product_name(name_raw: str | None) -> bool:
    if not name_raw: return False
    normalized = name_raw.casefold()
    if normalized.startswith(EXCLUDED_NAME_PREFIXES): return True
    return any(part in normalized for part in EXCLUDED_NAME_PARTS)


def build_product_rows(products: list[dict[str, Any]], stats: MoySkladCatalogSyncStats):
    rows, by_code, by_id = [], {}, {}

    for product in products:
        product_id = coerce_uuid(product.get("id"))
        if product_id is None:
            stats.skipped_products_invalid_system_id += 1
            continue

        external_code = optional_str(product.get("externalCode"))
        name_raw = optional_str(product.get("name"))

        if external_code and "#" in external_code:
            stats.skipped_products_variant_external_code += 1
            continue
        if is_excluded_product_name(name_raw):
            stats.skipped_products_excluded_name += 1
            continue

        if external_code: by_code[external_code] = product
        by_id[product_id] = product

        sku = fit_text(product.get("article") or product.get("code"), PRODUCT_SKU_MAX_LENGTH) or str(product_id)[:PRODUCT_SKU_MAX_LENGTH]
        name = fit_text(name_raw, PRODUCT_NAME_MAX_LENGTH) or sku[:PRODUCT_NAME_MAX_LENGTH]
        rows.append(MoySkladProductRow(system_id=product_id, sku=sku, name=name, description=normalize_product_text(product.get("description")), archived=False))

    return rows, by_code, by_id


def build_variant_rows(variants, stocks, products_by_code, products_by_id, stats, reserve: int = MOY_SKLAD_STOCK_RESERVE):
    rows, seen_products = [], set()
    stock_by_id, stock_by_code = build_stock_indexes(stocks)

    for variant in variants:
        variant_id = coerce_uuid(variant.get("id"))
        if variant_id is None:
            stats.skipped_variants_invalid_system_id += 1
            continue

        product_meta = variant.get("product") if isinstance(variant.get("product"), dict) else {}
        product_id = coerce_uuid(product_meta.get("id"))
        product = products_by_id.get(product_id) if product_id else None

        external_code = optional_str(product_meta.get("externalCode")) or optional_str(variant.get("externalCode"))
        if product is None and external_code: product = products_by_code.get(external_code)
        if product is None:
            stats.skipped_variants_missing_product += 1
            continue

        product_id = coerce_uuid(product.get("id"))
        if product_id is None:
            stats.skipped_variants_invalid_system_id += 1
            continue

        seen_products.add(product_id)
        stock = stock_by_id.get(variant_id) or stock_by_code.get(optional_str(variant.get("externalCode")) or "")
        sku = fit_text(variant.get("code"), VARIANT_SKU_MAX_LENGTH)
        fallback = sku or "Основной вариант"
        name = display_variant_name(variant.get("name"), product.get("name"), fallback)

        rows.append(MoySkladVariantRow(
            system_id=variant_id,
            product_system_id=product_id,
            sku=sku,
            name=fit_text(name, VARIANT_NAME_MAX_LENGTH) or fallback[:VARIANT_NAME_MAX_LENGTH],
            stock=available_stock((stock or {}).get("quantity"), reserve),
            price=sale_price(variant),
        ))

    add_synthetic_variants(rows, products_by_code, seen_products, stock_by_id, stock_by_code, reserve)
    return rows


def build_stock_indexes(stocks: list[dict[str, Any]]):
    by_id, by_code, duplicates = {}, {}, set()

    for stock in stocks:
        stock_id = assortment_id(stock)
        if stock_id: by_id[stock_id] = stock

        code = optional_str(stock.get("externalCode"))
        if code:
            if code in by_code: duplicates.add(code)
            by_code[code] = stock

    for code in duplicates: by_code.pop(code, None)
    return by_id, by_code


def add_synthetic_variants(rows, products_by_code, seen_products, stock_by_id, stock_by_code, reserve):
    for code, product in products_by_code.items():
        product_id = coerce_uuid(product.get("id"))
        if product_id is None or product_id in seen_products: continue

        stock = stock_by_id.get(product_id) or stock_by_code.get(code)
        rows.append(MoySkladVariantRow(
            system_id=synthetic_variant_id(product_id),
            product_system_id=product_id,
            sku=fit_text(product.get("code"), VARIANT_SKU_MAX_LENGTH),
            name="Основной вариант",
            stock=available_stock((stock or {}).get("quantity"), reserve),
            price=sale_price(product),
        ))
