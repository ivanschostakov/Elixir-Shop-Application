from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Product, ProductByCategory, ProductCategory

from .constants import LEGACY_CATEGORY_NAMES
from .schemas import WebsiteCatalogCategory, WebsiteCatalogSyncStats
from .utils import _category_name_key


def _legacy_category_candidates(remote_name: str) -> tuple[str, ...]:
    return LEGACY_CATEGORY_NAMES.get(_category_name_key(remote_name), ())


async def _sync_categories(session: AsyncSession, categories: list[WebsiteCatalogCategory] | None, products: list[Product], stats: WebsiteCatalogSyncStats) -> bool:
    if categories is None: return False

    existing_categories = list((await session.execute(select(ProductCategory))).scalars().all())
    existing_links = list((await session.execute(select(ProductByCategory))).scalars().all())
    categories_by_source_id = {category.website_category_id: category for category in existing_categories if category.website_category_id is not None}
    available_by_name: dict[str, list[ProductCategory]] = {}
    for category in existing_categories: available_by_name.setdefault(_category_name_key(category.name), []).append(category)

    assignments: list[tuple[WebsiteCatalogCategory, ProductCategory]] = []
    assigned_category_ids: set[int] = set()
    for remote in categories:
        category = categories_by_source_id.get(remote.source_id)
        if category is not None and category.id in assigned_category_ids: raise ValueError("A local category is assigned to more than one Bitrix category")
        if category is None:
            for candidate in available_by_name.get(_category_name_key(remote.name), []):
                if candidate.id not in assigned_category_ids:
                    category = candidate
                    break
        if category is None:
            for legacy_name in _legacy_category_candidates(remote.name):
                for candidate in available_by_name.get(legacy_name, []):
                    if candidate.id not in assigned_category_ids:
                        category = candidate
                        break
                if category is not None: break
        if category is None:
            category = ProductCategory(name=f"__bitrix_category_{remote.source_id}", description=None, archived=False, website_category_id=remote.source_id)
            session.add(category)
            await session.flush()
            existing_categories.append(category)
            stats.categories_created += 1
        else: stats.categories_matched += 1
        assigned_category_ids.add(category.id)
        assignments.append((remote, category))

    renamed_assignments = [(remote, category) for remote, category in assignments if category.name != remote.name]
    for remote, category in renamed_assignments: category.name = f"__bitrix_category_{remote.source_id}_{category.id}"
    if renamed_assignments: await session.flush()

    changed = bool(renamed_assignments) or stats.categories_created > 0
    for remote, category in assignments:
        if category.name != remote.name:
            category.name = remote.name
            stats.categories_renamed += 1
        if category.website_category_id != remote.source_id:
            category.website_category_id = remote.source_id
            stats.categories_linked += 1
            changed = True
        if category.archived:
            category.archived = False
            stats.categories_restored += 1
            changed = True

    for category in existing_categories:
        if category.id in assigned_category_ids or category.archived: continue
        category.archived = True
        stats.categories_archived += 1
        changed = True

    await session.flush()
    products_by_system_id = {product.system_id: product for product in products if product.system_id is not None}
    category_by_source_id = {remote.source_id: category for remote, category in assignments}
    desired_pairs: set[tuple[int, int]] = set()
    for remote in categories:
        category = category_by_source_id[remote.source_id]
        for system_id in remote.product_system_ids:
            product = products_by_system_id.get(system_id)
            if product is None:
                stats.category_links_skipped_missing_products += 1
                continue
            desired_pairs.add((product.id, category.id))

    existing_by_pair = {(link.product_id, link.category_id): link for link in existing_links}
    for pair, link in existing_by_pair.items():
        if pair in desired_pairs: continue
        await session.delete(link)
        stats.category_links_deleted += 1
        changed = True
    for product_id, category_id in desired_pairs:
        if (product_id, category_id) in existing_by_pair: continue
        session.add(ProductByCategory(product_id=product_id, category_id=category_id))
        stats.category_links_created += 1
        changed = True

    return changed
