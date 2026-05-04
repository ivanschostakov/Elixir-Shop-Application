import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.database import SessionLocal
from src.database.limits import (
    PRODUCT_NAME_MAX_LENGTH,
    PRODUCT_SKU_MAX_LENGTH,
    VARIANT_NAME_MAX_LENGTH,
    VARIANT_SKU_MAX_LENGTH,
)
from src.database.models import Product, Variant
from src.database.product_text import normalize_product_text
from src.normalize import coerce_decimal, coerce_int, coerce_uuid, fit_text
from src.scripts.remote_shop import remote_shop_database_url


@dataclass(frozen=True)
class RemoteProductRow:
    onec_id: str
    name: str
    code: str
    description: str | None
    usage: str | None
    expiration: str | None


@dataclass(frozen=True)
class RemoteFeatureRow:
    onec_id: str
    product_onec_id: str
    name: str
    code: str | None
    price: Decimal
    balance: int


async def fetch_remote_products_and_features() -> tuple[list[RemoteProductRow], list[RemoteFeatureRow]]:
    remote_engine = create_async_engine(remote_shop_database_url(), pool_pre_ping=True)
    try:
        async with remote_engine.connect() as conn:
            product_rows = await conn.execute(
                text(
                    """
                    select
                        p.onec_id,
                        p.name,
                        p.code,
                        p.description,
                        p.usage,
                        p.expiration
                    from public.products p
                    order by p.id
                    """
                )
            )
            feature_rows = await conn.execute(
                text(
                    """
                    select
                        f.onec_id,
                        f.product_onec_id,
                        f.name,
                        f.code,
                        f.price,
                        f.balance
                    from public.features f
                    order by f.id
                    """
                )
            )

            products = [
                RemoteProductRow(onec_id=onec_id, name=name, code=code, description=description, usage=usage, expiration=expiration)
                for onec_id, name, code, description, usage, expiration in product_rows
            ]
            features = [
                RemoteFeatureRow(
                    onec_id=onec_id,
                    product_onec_id=product_onec_id,
                    name=name,
                    code=code,
                    price=coerce_decimal(price) or Decimal("0"),
                    balance=coerce_int(balance) or 0,
                )
                for onec_id, product_onec_id, name, code, price, balance in feature_rows
            ]
            return products, features
    finally:
        await remote_engine.dispose()


async def sync_products_and_variants_from_shop() -> None:
    remote_products, remote_features = await fetch_remote_products_and_features()

    async with SessionLocal() as session:
        local_products = list((await session.execute(select(Product))).scalars().all())
        local_variants = list((await session.execute(select(Variant))).scalars().all())

        products_by_system_id = {product.system_id: product for product in local_products if product.system_id is not None}
        variants_by_system_id = {variant.system_id: variant for variant in local_variants if variant.system_id is not None}

        created_products = 0
        updated_products = 0
        created_variants = 0
        updated_variants = 0
        skipped_products_invalid_system_id = 0
        skipped_variants_invalid_system_id = 0
        skipped_variants_missing_product = 0

        for remote_product in remote_products:
            system_id = coerce_uuid(remote_product.onec_id)
            if system_id is None:
                skipped_products_invalid_system_id += 1
                continue

            payload = {
                "sku": fit_text(remote_product.code, PRODUCT_SKU_MAX_LENGTH),
                "name": fit_text(remote_product.name, PRODUCT_NAME_MAX_LENGTH),
                "description": normalize_product_text(remote_product.description),
                "usage": normalize_product_text(remote_product.usage),
                "expiration": normalize_product_text(remote_product.expiration),
            }

            local_product = products_by_system_id.get(system_id)
            if local_product is None:
                local_product = Product(system_id=system_id, priority=0, **payload)
                session.add(local_product)
                await session.flush()
                products_by_system_id[system_id] = local_product
                created_products += 1
                continue

            changed = False
            for field, value in payload.items():
                if getattr(local_product, field) != value:
                    setattr(local_product, field, value)
                    changed = True
            if changed:
                updated_products += 1

        await session.flush()

        for remote_feature in remote_features:
            system_id = coerce_uuid(remote_feature.onec_id)
            product_system_id = coerce_uuid(remote_feature.product_onec_id)
            if system_id is None or product_system_id is None:
                skipped_variants_invalid_system_id += 1
                continue

            local_product = products_by_system_id.get(product_system_id)
            if local_product is None:
                skipped_variants_missing_product += 1
                continue

            payload = {
                "product_id": local_product.id,
                "sku": fit_text(remote_feature.code, VARIANT_SKU_MAX_LENGTH),
                "name": fit_text(remote_feature.name, VARIANT_NAME_MAX_LENGTH),
                "stock": max(coerce_int(remote_feature.balance) or 0, 0),
                "price": remote_feature.price,
            }

            local_variant = variants_by_system_id.get(system_id)
            if local_variant is None:
                local_variant = Variant(system_id=system_id, **payload)
                session.add(local_variant)
                variants_by_system_id[system_id] = local_variant
                created_variants += 1
                continue

            changed = False
            for field, value in payload.items():
                if getattr(local_variant, field) != value:
                    setattr(local_variant, field, value)
                    changed = True
            if changed:
                updated_variants += 1

        await session.commit()

    print(f"remote_products={len(remote_products)}")
    print(f"remote_features={len(remote_features)}")
    print(f"created_products={created_products}")
    print(f"updated_products={updated_products}")
    print(f"created_variants={created_variants}")
    print(f"updated_variants={updated_variants}")
    print(f"skipped_products_invalid_system_id={skipped_products_invalid_system_id}")
    print(f"skipped_variants_invalid_system_id={skipped_variants_invalid_system_id}")
    print(f"skipped_variants_missing_product={skipped_variants_missing_product}")


if __name__ == "__main__":
    asyncio.run(sync_products_and_variants_from_shop())
