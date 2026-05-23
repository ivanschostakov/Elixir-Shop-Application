import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.cache import get_cache_service
from src.database import SessionLocal
from src.database.models import Product, Variant

from .client import get_moysklad_client
from .schemas import MoySkladCatalogSyncStats, MoySkladProductRow, MoySkladVariantRow

logger = logging.getLogger(__name__)


async def upsert_catalog_rows(session: AsyncSession, products: list[MoySkladProductRow], variants: list[MoySkladVariantRow], stats: MoySkladCatalogSyncStats | None = None):
    stats = stats or MoySkladCatalogSyncStats(fetched_products=len(products), fetched_variants=len(variants))

    local_products = list((await session.execute(select(Product))).scalars())
    local_variants = list((await session.execute(select(Variant))).scalars())

    products_by_system_id = {p.system_id: p for p in local_products if p.system_id is not None}
    products_by_sku = {p.sku: p for p in local_products}
    products_by_name = {p.name: p for p in local_products}
    variants_by_system_id = {v.system_id: v for v in local_variants if v.system_id is not None}
    variants_by_product_id: dict[int, list[Variant]] = defaultdict(list)

    for variant in local_variants: variants_by_product_id[variant.product_id].append(variant)

    incoming_product_ids = {p.system_id for p in products}
    incoming_variant_ids = {v.system_id for v in variants}

    await upsert_products(session, products, stats, products_by_system_id, products_by_sku, products_by_name, variants_by_product_id)
    archive_missing_products(local_products, incoming_product_ids, stats)
    await session.flush()

    await upsert_variants(session, variants, stats, products_by_system_id, variants_by_system_id, variants_by_product_id)
    archive_missing_variants(local_variants, incoming_variant_ids, stats)
    update_product_stock(products_by_system_id.values(), incoming_product_ids, variants_by_product_id, stats)

    logger.info("MoySklad catalog DB upsert prepared stats=%s", stats.as_dict())
    return stats


async def upsert_products(session, products, stats, by_id, by_sku, by_name, variants_by_product_id):
    for row in products:
        product = by_id.get(row.system_id)

        if product is None:
            if row.sku in by_sku:
                stats.skipped_products_conflict_sku += 1
                continue
            if row.name in by_name:
                stats.skipped_products_conflict_name += 1
                continue

            product = Product(system_id=row.system_id, sku=row.sku, name=row.name, archived=row.archived, priority=0)
            session.add(product)
            await session.flush()

            by_id[row.system_id] = product
            by_sku[product.sku] = product
            by_name[product.name] = product
            variants_by_product_id.setdefault(product.id, [])
            stats.created_products += 1
            continue

        payload = {"sku": row.sku, "name": row.name}
        if row.archived: payload["archived"] = True

        if by_sku.get(row.sku) not in (None, product):
            payload.pop("sku", None)
            stats.skipped_products_conflict_sku += 1
        if by_name.get(row.name) not in (None, product):
            payload.pop("name", None)
            stats.skipped_products_conflict_name += 1

        if apply_changes(product, payload): stats.updated_products += 1


async def upsert_variants(session, variants, stats, products_by_id, variants_by_id, variants_by_product_id):
    for row in variants:
        product = products_by_id.get(row.product_system_id)
        if product is None:
            stats.skipped_variants_missing_product += 1
            continue

        payload = {"product_id": product.id, "sku": row.sku, "name": row.name, "stock": row.stock, "price": row.price}
        variant = variants_by_id.get(row.system_id)

        if variant is None:
            variant = Variant(system_id=row.system_id, archived=product.archived, **payload)
            session.add(variant)
            variants_by_id[row.system_id] = variant
            variants_by_product_id.setdefault(product.id, []).append(variant)
            stats.created_variants += 1
            continue

        if product.archived: payload["archived"] = True
        if apply_changes(variant, payload): stats.updated_variants += 1


def archive_missing_products(products, incoming_ids, stats):
    for product in products:
        if product.system_id in incoming_ids or product.archived: continue
        product.archived = True
        product.in_stock = False
        stats.archived_products += 1
        stats.updated_products += 1


def archive_missing_variants(variants, incoming_ids, stats):
    for variant in variants:
        if variant.system_id in incoming_ids: continue
        if variant.stock == 0 and variant.archived: continue
        variant.stock = 0
        variant.archived = True
        stats.missing_variants_archived += 1
        stats.updated_variants += 1


def update_product_stock(products, incoming_ids, variants_by_product_id, stats):
    for product in products:
        in_stock = product.system_id in incoming_ids and not product.archived and any(not v.archived and v.stock > 0 for v in variants_by_product_id.get(product.id, []))
        if product.in_stock == in_stock: continue
        product.in_stock = in_stock
        stats.updated_products += 1


async def sync_moysklad_product_catalog():
    started = time.perf_counter()
    moysklad_client = get_moysklad_client()
    product_rows, variant_rows, stats = moysklad_client.fetch_catalog_rows()

    async with SessionLocal() as session:
        try:
            stats = await upsert_catalog_rows(session, product_rows, variant_rows, stats)
            await session.commit()

            cache = get_cache_service()
            await cache.bump_namespace("catalog")
            await cache.bump_namespace("product")

            logger.info("MoySklad catalog sync committed stats=%s seconds=%.2f", stats.as_dict(), time.perf_counter() - started)
            return stats

        except Exception:
            await session.rollback()
            logger.exception("MoySklad catalog sync rolled back")
            raise


def apply_changes(model: Any, payload: dict[str, Any]) -> bool:
    changed = False
    for field, value in payload.items():
        if getattr(model, field) == value: continue
        setattr(model, field, value)
        changed = True
    return changed