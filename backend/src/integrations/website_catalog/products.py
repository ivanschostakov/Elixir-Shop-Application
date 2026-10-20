from src.database.models import Product

from .schemas import WebsiteCatalogContent, WebsiteCatalogSyncStats
from .utils import _sku


def _match_content_rows(products: list[Product], contents: list[WebsiteCatalogContent], stats: WebsiteCatalogSyncStats) -> list[tuple[Product, WebsiteCatalogContent]]:
    local_by_system_id = {product.system_id: product for product in products if product.system_id is not None}
    local_by_sku: dict[str, list[Product]] = {}
    for product in products:
        sku = _sku(product.sku)
        if sku is not None: local_by_sku.setdefault(sku, []).append(product)
    remote_by_sku: dict[str, list[WebsiteCatalogContent]] = {}
    for content in contents:
        if content.sku is not None: remote_by_sku.setdefault(content.sku, []).append(content)

    matched: list[tuple[Product, WebsiteCatalogContent]] = []
    assigned_product_ids: set[int] = set()
    for content in contents:
        product = (local_by_system_id.get(content.system_id) if content.system_id is not None else None)
        match_kind = "system_id" if product is not None else None
        if product is None and content.sku is not None:
            remote_sku_rows = remote_by_sku.get(content.sku, [])
            local_sku_rows = local_by_sku.get(content.sku, [])
            if len(remote_sku_rows) > 1 or len(local_sku_rows) > 1:
                stats.skipped_ambiguous_sku += 1
                continue
            if len(remote_sku_rows) == 1 and len(local_sku_rows) == 1:
                product = local_sku_rows[0]
                match_kind = "sku"
        if product is None:
            stats.skipped_missing_product += 1
            continue

        product_key = int(product.id) if product.id is not None else id(product)
        if product_key in assigned_product_ids:
            stats.skipped_ambiguous_sku += 1
            continue
        assigned_product_ids.add(product_key)
        matched.append((product, content))
        if match_kind == "system_id": stats.matched_by_system_id += 1
        else: stats.matched_by_sku += 1

    stats.matched = len(matched)
    return matched


def _apply_content(product: Product, content: WebsiteCatalogContent, stats: WebsiteCatalogSyncStats) -> bool:
    changed = False
    for field, value, counter in (
        ("description", content.description, "updated_description"),
        ("usage", content.usage, "updated_usage"),
        ("expiration", content.storage, "updated_storage"),
    ):
        if getattr(product, field) == value: continue
        setattr(product, field, value)
        setattr(stats, counter, getattr(stats, counter) + 1)
        changed = True
    return changed
