import asyncio
import os
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.database import SessionLocal
from src.database.models import Product, ProductByCategory, ProductCategory
from src.normalize import casefold_optional_str, lower_optional_str, optional_str


@dataclass(frozen=True)
class RemoteTgCategoryRow:
    remote_id: int
    category_name: str
    description: str | None


@dataclass(frozen=True)
class RemoteProductCategoryLinkRow:
    product_onec_id: str
    remote_category_id: int


def _remote_database_url() -> str:
    user = os.environ["SHOP_POSTGRES_USER"]
    password = os.environ["SHOP_POSTGRES_PASSWORD"]
    host = os.environ["SHOP_POSTGRES_HOST"]
    port = os.environ.get("SHOP_POSTGRES_PORT", "5432")
    database = os.environ["SHOP_POSTGRES_DB"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def _normalize_category_name(value: str | None) -> str | None:
    normalized = optional_str(value)
    if normalized is None or normalized == "<Без категории>":
        return None
    return normalized


async def fetch_remote_product_categories() -> tuple[list[RemoteTgCategoryRow], list[RemoteProductCategoryLinkRow]]:
    remote_engine = create_async_engine(_remote_database_url(), pool_pre_ping=True)
    try:
        async with remote_engine.connect() as conn:
            category_rows = await conn.execute(
                text(
                    """
                    select
                        c.id as remote_id,
                        c.name as category_name,
                        c.description as description
                    from public.tg_categories c
                    order by c.id
                    """
                )
            )
            link_rows = await conn.execute(
                text(
                    """
                    select distinct
                        pc.product_onec_id as product_onec_id,
                        pc.tg_category_id as remote_category_id
                    from public.product_tg_categories pc
                    where pc.product_onec_id is not null
                      and pc.tg_category_id is not null
                    order by pc.tg_category_id, pc.product_onec_id
                    """
                )
            )

            categories: list[RemoteTgCategoryRow] = []
            for remote_id, category_name, description in category_rows:
                normalized_category_name = _normalize_category_name(category_name)
                if normalized_category_name is None:
                    continue
                categories.append(
                    RemoteTgCategoryRow(
                        remote_id=remote_id, category_name=normalized_category_name, description=optional_str(description)
                    )
                )

            links: list[RemoteProductCategoryLinkRow] = []
            for product_onec_id, remote_category_id in link_rows:
                normalized_onec_id = lower_optional_str(product_onec_id)
                if normalized_onec_id is None:
                    continue
                links.append(RemoteProductCategoryLinkRow(product_onec_id=normalized_onec_id, remote_category_id=remote_category_id))

            return categories, links
    finally:
        await remote_engine.dispose()


async def import_product_categories_from_shop() -> None:
    remote_categories, remote_links = await fetch_remote_product_categories()

    remote_categories_by_id = {category.remote_id: category for category in remote_categories}
    desired_category_names = {
        category_key
        for category in remote_categories
        if (category_key := casefold_optional_str(category.category_name)) is not None
    }

    async with SessionLocal() as session:
        local_products = list((await session.execute(select(Product))).scalars().all())
        local_categories = list((await session.execute(select(ProductCategory))).scalars().all())
        local_links = list((await session.execute(select(ProductByCategory))).scalars().all())

        products_by_system_id = {
            product_key: product
            for product in local_products
            if (product_key := lower_optional_str(product.system_id)) is not None
        }
        categories_by_name = {
            category_key: category
            for category in local_categories
            if (category_key := casefold_optional_str(category.name)) is not None
        }

        created_categories = 0
        updated_categories = 0
        deleted_categories = 0
        created_links = 0
        deleted_links = 0
        skipped_missing_products = 0
        skipped_missing_categories = 0

        for remote_category in remote_categories:
            category_key = casefold_optional_str(remote_category.category_name)
            assert category_key is not None
            category = categories_by_name.get(category_key)
            if category is None:
                category = ProductCategory(name=remote_category.category_name, description=remote_category.description)
                session.add(category)
                await session.flush()
                categories_by_name[category_key] = category
                created_categories += 1
                continue

            if category.description != remote_category.description:
                category.description = remote_category.description
                updated_categories += 1

        desired_pairs: set[tuple[int, int]] = set()
        for remote_link in remote_links:
            remote_category = remote_categories_by_id.get(remote_link.remote_category_id)
            if remote_category is None:
                skipped_missing_categories += 1
                continue

            product = products_by_system_id.get(remote_link.product_onec_id)
            if product is None:
                skipped_missing_products += 1
                continue

            category_key = casefold_optional_str(remote_category.category_name)
            assert category_key is not None
            category = categories_by_name[category_key]
            desired_pairs.add((product.id, category.id))

        existing_pairs = {(link.product_id, link.category_id): link for link in local_links}

        for pair, link in existing_pairs.items():
            if pair in desired_pairs:
                continue
            await session.delete(link)
            deleted_links += 1

        for product_id, category_id in desired_pairs:
            if (product_id, category_id) in existing_pairs:
                continue
            session.add(ProductByCategory(product_id=product_id, category_id=category_id))
            created_links += 1

        stale_categories = [
            category
            for category in categories_by_name.values()
            if (casefold_optional_str(category.name) or "") not in desired_category_names
        ]
        for category in stale_categories:
            await session.delete(category)
            deleted_categories += 1

        await session.commit()

    print(f"remote_categories={len(remote_categories)}")
    print(f"remote_links={len(remote_links)}")
    print(f"created_categories={created_categories}")
    print(f"updated_categories={updated_categories}")
    print(f"deleted_categories={deleted_categories}")
    print(f"created_links={created_links}")
    print(f"deleted_links={deleted_links}")
    print(f"skipped_missing_products={skipped_missing_products}")
    print(f"skipped_missing_categories={skipped_missing_categories}")


if __name__ == "__main__":
    asyncio.run(import_product_categories_from_shop())
