from typing import Any
from urllib.parse import unquote, urljoin, urlsplit
from uuid import UUID

from src.integrations.website_catalog_certificates import MAX_CERTIFICATE_SIZE_BYTES
from src.normalize import coerce_uuid

from .constants import MAX_CATEGORIES, MAX_CATEGORY_LINKS, MAX_CERTIFICATES_PER_PRODUCT, MAX_PRODUCTS
from .schemas import WebsiteCatalogCategory, WebsiteCatalogCertificate, WebsiteCatalogContent, WebsiteCatalogSyncStats
from .utils import _category_name_key, _content, _short_text, _sku


def _parse_certificates(row: dict[str, Any], *, public_base_url: str | None, stats: WebsiteCatalogSyncStats) -> tuple[WebsiteCatalogCertificate, ...] | None:
    if "certificates" not in row: return None
    raw_certificates = row["certificates"]
    if not isinstance(raw_certificates, list): raise ValueError("Product certificates must be a list")
    if len(raw_certificates) > MAX_CERTIFICATES_PER_PRODUCT: raise ValueError("Product contains too many certificates")
    if raw_certificates and not public_base_url: raise ValueError("Certificate base URL is not configured")

    parsed: list[WebsiteCatalogCertificate] = []
    seen_file_ids: set[int] = set()
    for raw_certificate in raw_certificates:
        if not isinstance(raw_certificate, dict): raise ValueError("Certificate entry must be an object")
        source_file_id = raw_certificate.get("source_file_id")
        if (isinstance(source_file_id, bool) or not isinstance(source_file_id, int) or source_file_id <= 0): raise ValueError("Certificate source file ID is invalid")
        if source_file_id in seen_file_ids: raise ValueError("Certificate source file ID is duplicated")
        seen_file_ids.add(source_file_id)

        path = _short_text(raw_certificate.get("path"), max_length=1500, required=True)
        assert path is not None
        parsed_path = urlsplit(path)
        if (not path.startswith("/upload/") or parsed_path.scheme or parsed_path.netloc or parsed_path.query or parsed_path.fragment or ".." in unquote(parsed_path.path).split("/")): raise ValueError("Certificate path is invalid")
        size_bytes = raw_certificate.get("size_bytes", 0)
        if (isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0 or size_bytes > MAX_CERTIFICATE_SIZE_BYTES): raise ValueError("Certificate file size is invalid")

        title = _short_text(raw_certificate.get("title"), max_length=500, required=True)
        assert title is not None
        parsed.append(WebsiteCatalogCertificate(source_file_id=source_file_id, title=title, original_name=_short_text(raw_certificate.get("original_name"), max_length=500), content_type=_short_text(raw_certificate.get("content_type"), max_length=255), size_bytes=size_bytes, source_url=urljoin(public_base_url, path)))

    stats.certificates_fetched += len(parsed)
    return tuple(parsed)


def _parse_content_rows(payload: dict[str, Any], stats: WebsiteCatalogSyncStats, *, public_base_url: str | None = None) -> list[WebsiteCatalogContent]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list): raise ValueError("Catalog sync response does not contain a product list")
    if len(raw_products) > MAX_PRODUCTS: raise ValueError("Catalog sync response contains too many products")

    stats.fetched = len(raw_products)
    parsed: list[WebsiteCatalogContent] = []
    seen_system_ids: set[UUID] = set()
    duplicates: set[UUID] = set()
    for row in raw_products:
        if not isinstance(row, dict):
            stats.skipped_invalid_system_id += 1
            continue
        system_id = coerce_uuid(row.get("system_id"))
        sku = _sku(row.get("sku"))
        if system_id is None and sku is None:
            stats.skipped_invalid_system_id += 1
            continue
        if system_id is not None and system_id in seen_system_ids:
            duplicates.add(system_id)
            continue
        if system_id is not None: seen_system_ids.add(system_id)
        parsed.append(WebsiteCatalogContent(system_id=system_id, sku=sku, description=_content(row.get("description")), usage=_content(row.get("usage")), storage=_content(row.get("storage")), certificates=_parse_certificates(row, public_base_url=public_base_url, stats=stats)))

    parsed = [content for content in parsed if content.system_id not in duplicates]
    stats.skipped_duplicate_system_id = len(duplicates)
    return parsed


def _parse_categories(payload: dict[str, Any], stats: WebsiteCatalogSyncStats) -> list[WebsiteCatalogCategory] | None:
    if "categories" not in payload: return None
    raw_categories = payload["categories"]
    if not isinstance(raw_categories, list): raise ValueError("Catalog categories must be a list")
    if len(raw_categories) > MAX_CATEGORIES: raise ValueError("Catalog response contains too many categories")

    categories: list[WebsiteCatalogCategory] = []
    seen_source_ids: set[int] = set()
    seen_names: set[str] = set()
    total_links = 0
    for row in raw_categories:
        if not isinstance(row, dict): raise ValueError("Catalog category entry must be an object")
        source_id = row.get("source_id")
        if (isinstance(source_id, bool) or not isinstance(source_id, int) or source_id <= 0 or source_id in seen_source_ids): raise ValueError("Catalog category source ID is invalid or duplicated")
        name = _short_text(row.get("name"), max_length=200, required=True)
        assert name is not None
        name_key = _category_name_key(name)
        if name_key in seen_names: raise ValueError("Active Bitrix category names must be unique")
        seen_source_ids.add(source_id)
        seen_names.add(name_key)

        raw_system_ids = row.get("product_system_ids")
        if not isinstance(raw_system_ids, list): raise ValueError("Catalog category product IDs must be a list")
        product_system_ids: list[UUID] = []
        seen_product_system_ids: set[UUID] = set()
        for raw_system_id in raw_system_ids:
            system_id = coerce_uuid(raw_system_id)
            if system_id is None: raise ValueError("Catalog category contains an invalid product ID")
            if system_id in seen_product_system_ids: continue
            seen_product_system_ids.add(system_id)
            product_system_ids.append(system_id)
        total_links += len(product_system_ids)
        if total_links > MAX_CATEGORY_LINKS: raise ValueError("Catalog response contains too many category links")
        categories.append(WebsiteCatalogCategory(source_id=source_id, name=name, product_system_ids=tuple(product_system_ids)))

    stats.categories_fetched = len(categories)
    return categories
