from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import (
    WEBSITE_CATALOG_PUBLIC_BASE_URL,
    WEBSITE_CATALOG_SYNC_ENDPOINT,
    WEBSITE_CATALOG_SYNC_SECRET,
    WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS,
)
from src.app.services.cache import get_cache_service
from src.database.models import (
    Product,
    ProductByCategory,
    ProductCategory,
    ProductCertificate,
)
from src.integrations.website_catalog_certificates import (
    MAX_CERTIFICATE_SIZE_BYTES,
    certificate_local_path_from_url,
    mirror_certificate,
    remove_local_certificate,
)
from src.normalize import coerce_uuid


log = logging.getLogger("integrations.website_catalog")
MAX_PRODUCTS = 500
MAX_CATEGORIES = 200
MAX_CATEGORY_LINKS = 10_000
MAX_CERTIFICATES_PER_PRODUCT = 50
MAX_CONTENT_LENGTH = 200_000

LEGACY_CATEGORY_NAMES: dict[str, tuple[str, ...]] = {
    "все пептиды": ("пептиды",),
    "стройность без усилий": ("снижение веса и жиросжигатели",),
    "косметические пептиды (кожа, волосы, загар)": ("косметические пептиды",),
    "мужское и женское здоровье": ("мужское и женское здоровье",),
    "для иммунной системы": ("для имунной системы",),
    "антидепресанты": ("антидепрессанты",),
}


@dataclass
class WebsiteCatalogSyncStats:
    fetched: int = 0
    matched: int = 0
    matched_by_system_id: int = 0
    matched_by_sku: int = 0
    updated_products: int = 0
    updated_description: int = 0
    updated_usage: int = 0
    updated_storage: int = 0
    unchanged: int = 0
    skipped_invalid_system_id: int = 0
    skipped_duplicate_system_id: int = 0
    skipped_ambiguous_sku: int = 0
    skipped_missing_product: int = 0
    categories_fetched: int = 0
    categories_matched: int = 0
    categories_linked: int = 0
    categories_created: int = 0
    categories_renamed: int = 0
    categories_restored: int = 0
    categories_archived: int = 0
    category_links_created: int = 0
    category_links_deleted: int = 0
    category_links_skipped_missing_products: int = 0
    certificates_fetched: int = 0
    certificates_created: int = 0
    certificates_updated: int = 0
    certificates_deleted: int = 0
    certificates_downloaded: int = 0
    certificate_bytes_downloaded: int = 0
    certificate_files_deleted: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class WebsiteCatalogContent:
    system_id: UUID | None
    sku: str | None
    description: str | None
    usage: str | None
    storage: str | None
    certificates: tuple["WebsiteCatalogCertificate", ...] | None = None


@dataclass(frozen=True)
class WebsiteCatalogCertificate:
    source_file_id: int
    title: str
    original_name: str | None
    content_type: str | None
    size_bytes: int
    source_url: str


@dataclass(frozen=True)
class WebsiteCatalogCategory:
    source_id: int
    name: str
    product_system_ids: tuple[UUID, ...]


def website_catalog_sync_configured() -> bool:
    return bool(WEBSITE_CATALOG_SYNC_ENDPOINT and WEBSITE_CATALOG_SYNC_SECRET)


class WebsiteCatalogSyncClient:
    def __init__(
        self,
        *,
        endpoint: str | None = WEBSITE_CATALOG_SYNC_ENDPOINT,
        secret: str | None = WEBSITE_CATALOG_SYNC_SECRET,
        public_base_url: str | None = WEBSITE_CATALOG_PUBLIC_BASE_URL,
        timeout: int = WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoint or not secret:
            raise RuntimeError("Website catalog sync is not configured")
        parsed_endpoint = urlsplit(endpoint)
        if (
            parsed_endpoint.scheme != "https"
            or parsed_endpoint.hostname is None
            or parsed_endpoint.username is not None
            or parsed_endpoint.password is not None
        ):
            raise RuntimeError("Website catalog sync endpoint must be an HTTPS URL without credentials")
        derived_public_base_url = (
            public_base_url
            or f"{parsed_endpoint.scheme}://{parsed_endpoint.hostname}"
        )
        parsed_public_base_url = urlsplit(derived_public_base_url)
        if (
            parsed_public_base_url.scheme != "https"
            or parsed_public_base_url.hostname is None
            or parsed_public_base_url.username is not None
            or parsed_public_base_url.password is not None
            or parsed_public_base_url.path not in ("", "/")
            or parsed_public_base_url.query
            or parsed_public_base_url.fragment
        ):
            raise RuntimeError("Website catalog public base URL must be an HTTPS origin")
        if len(secret) < 32:
            raise RuntimeError("Website catalog sync secret must contain at least 32 characters")
        self.endpoint = endpoint
        self.public_base_url = (
            f"{parsed_public_base_url.scheme}://{parsed_public_base_url.netloc}/"
        )
        self.secret = secret.encode("utf-8")
        self.timeout = timeout
        self.transport = transport

    async def pull(self) -> dict[str, Any]:
        body = json.dumps(
            {"action": "pull"},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.secret,
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(
                self.endpoint,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Elixir-Timestamp": timestamp,
                    "X-Elixir-Signature": signature,
                },
            )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError(
                str(result.get("error") if isinstance(result, dict) else "Invalid catalog sync response")
            )
        return result


def _content(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Catalog content fields must be strings or null")
    normalized = value.replace("\x00", "").strip()
    if not normalized:
        return None
    if len(normalized) > MAX_CONTENT_LENGTH:
        raise ValueError("Catalog content field is too long")
    return normalized


def _sku(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("\x00", "").strip().casefold()
    return normalized[:256] or None


def _short_text(value: Any, *, max_length: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError("Required catalog text field is missing")
        return None
    if not isinstance(value, str):
        raise ValueError("Catalog text fields must be strings or null")
    normalized = value.replace("\x00", "").strip()
    if not normalized:
        if required:
            raise ValueError("Required catalog text field is empty")
        return None
    if len(normalized) > max_length:
        raise ValueError("Catalog text field is too long")
    return normalized


def _parse_certificates(
    row: dict[str, Any],
    *,
    public_base_url: str | None,
    stats: WebsiteCatalogSyncStats,
) -> tuple[WebsiteCatalogCertificate, ...] | None:
    if "certificates" not in row:
        return None
    raw_certificates = row["certificates"]
    if not isinstance(raw_certificates, list):
        raise ValueError("Product certificates must be a list")
    if len(raw_certificates) > MAX_CERTIFICATES_PER_PRODUCT:
        raise ValueError("Product contains too many certificates")
    if raw_certificates and not public_base_url:
        raise ValueError("Certificate base URL is not configured")

    parsed: list[WebsiteCatalogCertificate] = []
    seen_file_ids: set[int] = set()
    for raw_certificate in raw_certificates:
        if not isinstance(raw_certificate, dict):
            raise ValueError("Certificate entry must be an object")
        source_file_id = raw_certificate.get("source_file_id")
        if (
            isinstance(source_file_id, bool)
            or not isinstance(source_file_id, int)
            or source_file_id <= 0
        ):
            raise ValueError("Certificate source file ID is invalid")
        if source_file_id in seen_file_ids:
            raise ValueError("Certificate source file ID is duplicated")
        seen_file_ids.add(source_file_id)

        path = _short_text(raw_certificate.get("path"), max_length=1500, required=True)
        assert path is not None
        parsed_path = urlsplit(path)
        if (
            not path.startswith("/upload/")
            or parsed_path.scheme
            or parsed_path.netloc
            or parsed_path.query
            or parsed_path.fragment
            or ".." in unquote(parsed_path.path).split("/")
        ):
            raise ValueError("Certificate path is invalid")
        size_bytes = raw_certificate.get("size_bytes", 0)
        if (
            isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
            or size_bytes > MAX_CERTIFICATE_SIZE_BYTES
        ):
            raise ValueError("Certificate file size is invalid")

        title = _short_text(raw_certificate.get("title"), max_length=500, required=True)
        assert title is not None
        parsed.append(WebsiteCatalogCertificate(
            source_file_id=source_file_id,
            title=title,
            original_name=_short_text(raw_certificate.get("original_name"), max_length=500),
            content_type=_short_text(raw_certificate.get("content_type"), max_length=255),
            size_bytes=size_bytes,
            source_url=urljoin(public_base_url, path),
        ))

    stats.certificates_fetched += len(parsed)
    return tuple(parsed)


def _parse_content_rows(
    payload: dict[str, Any],
    stats: WebsiteCatalogSyncStats,
    *,
    public_base_url: str | None = None,
) -> list[WebsiteCatalogContent]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise ValueError("Catalog sync response does not contain a product list")
    if len(raw_products) > MAX_PRODUCTS:
        raise ValueError("Catalog sync response contains too many products")

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
        if system_id is not None:
            seen_system_ids.add(system_id)
        parsed.append(WebsiteCatalogContent(
            system_id=system_id,
            sku=sku,
            description=_content(row.get("description")),
            usage=_content(row.get("usage")),
            storage=_content(row.get("storage")),
            certificates=_parse_certificates(
                row,
                public_base_url=public_base_url,
                stats=stats,
            ),
        ))

    parsed = [
        content
        for content in parsed
        if content.system_id not in duplicates
    ]
    stats.skipped_duplicate_system_id = len(duplicates)
    return parsed


def _category_name_key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _parse_categories(
    payload: dict[str, Any],
    stats: WebsiteCatalogSyncStats,
) -> list[WebsiteCatalogCategory] | None:
    if "categories" not in payload:
        return None
    raw_categories = payload["categories"]
    if not isinstance(raw_categories, list):
        raise ValueError("Catalog categories must be a list")
    if len(raw_categories) > MAX_CATEGORIES:
        raise ValueError("Catalog response contains too many categories")

    categories: list[WebsiteCatalogCategory] = []
    seen_source_ids: set[int] = set()
    seen_names: set[str] = set()
    total_links = 0
    for row in raw_categories:
        if not isinstance(row, dict):
            raise ValueError("Catalog category entry must be an object")
        source_id = row.get("source_id")
        if (
            isinstance(source_id, bool)
            or not isinstance(source_id, int)
            or source_id <= 0
            or source_id in seen_source_ids
        ):
            raise ValueError("Catalog category source ID is invalid or duplicated")
        name = _short_text(row.get("name"), max_length=200, required=True)
        assert name is not None
        name_key = _category_name_key(name)
        if name_key in seen_names:
            raise ValueError("Active Bitrix category names must be unique")
        seen_source_ids.add(source_id)
        seen_names.add(name_key)

        raw_system_ids = row.get("product_system_ids")
        if not isinstance(raw_system_ids, list):
            raise ValueError("Catalog category product IDs must be a list")
        product_system_ids: list[UUID] = []
        seen_product_system_ids: set[UUID] = set()
        for raw_system_id in raw_system_ids:
            system_id = coerce_uuid(raw_system_id)
            if system_id is None:
                raise ValueError("Catalog category contains an invalid product ID")
            if system_id in seen_product_system_ids:
                continue
            seen_product_system_ids.add(system_id)
            product_system_ids.append(system_id)
        total_links += len(product_system_ids)
        if total_links > MAX_CATEGORY_LINKS:
            raise ValueError("Catalog response contains too many category links")
        categories.append(WebsiteCatalogCategory(
            source_id=source_id,
            name=name,
            product_system_ids=tuple(product_system_ids),
        ))

    stats.categories_fetched = len(categories)
    return categories


def _match_content_rows(
    products: list[Product],
    contents: list[WebsiteCatalogContent],
    stats: WebsiteCatalogSyncStats,
) -> list[tuple[Product, WebsiteCatalogContent]]:
    local_by_system_id = {
        product.system_id: product
        for product in products
        if product.system_id is not None
    }
    local_by_sku: dict[str, list[Product]] = {}
    for product in products:
        sku = _sku(product.sku)
        if sku is not None:
            local_by_sku.setdefault(sku, []).append(product)
    remote_by_sku: dict[str, list[WebsiteCatalogContent]] = {}
    for content in contents:
        if content.sku is not None:
            remote_by_sku.setdefault(content.sku, []).append(content)

    matched: list[tuple[Product, WebsiteCatalogContent]] = []
    assigned_product_ids: set[int] = set()
    for content in contents:
        product = (
            local_by_system_id.get(content.system_id)
            if content.system_id is not None
            else None
        )
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
        if match_kind == "system_id":
            stats.matched_by_system_id += 1
        else:
            stats.matched_by_sku += 1

    stats.matched = len(matched)
    return matched


def _apply_content(
    product: Product,
    content: WebsiteCatalogContent,
    stats: WebsiteCatalogSyncStats,
) -> bool:
    changed = False
    for field, value, counter in (
        ("description", content.description, "updated_description"),
        ("usage", content.usage, "updated_usage"),
        ("expiration", content.storage, "updated_storage"),
    ):
        if getattr(product, field) == value:
            continue
        setattr(product, field, value)
        setattr(stats, counter, getattr(stats, counter) + 1)
        changed = True
    return changed


async def _apply_certificates(
    session: AsyncSession,
    product: Product,
    certificates: tuple[WebsiteCatalogCertificate, ...] | None,
    stats: WebsiteCatalogSyncStats,
    *,
    download_client: httpx.AsyncClient,
    downloaded_paths: set[Path],
    stale_paths: set[Path],
) -> bool:
    if certificates is None:
        return False

    changed = False
    existing_by_file_id = {
        certificate.website_file_id: certificate
        for certificate in product.certificates
    }
    desired_file_ids = {certificate.source_file_id for certificate in certificates}

    for sort_order, remote in enumerate(certificates):
        certificate = existing_by_file_id.get(remote.source_file_id)
        mirrored = await mirror_certificate(
            download_client,
            product_id=product.id,
            source_file_id=remote.source_file_id,
            source_url=remote.source_url,
            original_name=remote.original_name,
            content_type=remote.content_type,
            expected_size_bytes=remote.size_bytes,
        )
        if mirrored.downloaded:
            downloaded_paths.add(mirrored.path)
            stats.certificates_downloaded += 1
            stats.certificate_bytes_downloaded += mirrored.size_bytes
        if certificate is None:
            session.add(ProductCertificate(
                product_id=product.id,
                website_file_id=remote.source_file_id,
                title=remote.title,
                original_name=remote.original_name,
                content_type=mirrored.content_type,
                size_bytes=mirrored.size_bytes,
                url=mirrored.url,
                sort_order=sort_order,
            ))
            stats.certificates_created += 1
            changed = True
            continue

        previous_path = certificate_local_path_from_url(certificate.url)
        certificate_changed = False
        for field, value in (
            ("title", remote.title),
            ("original_name", remote.original_name),
            ("content_type", mirrored.content_type),
            ("size_bytes", mirrored.size_bytes),
            ("url", mirrored.url),
            ("sort_order", sort_order),
        ):
            if getattr(certificate, field) == value:
                continue
            setattr(certificate, field, value)
            certificate_changed = True
        if certificate_changed:
            stats.certificates_updated += 1
            changed = True
        if previous_path is not None and previous_path != mirrored.path:
            stale_paths.add(previous_path)

    for source_file_id, certificate in existing_by_file_id.items():
        if source_file_id in desired_file_ids:
            continue
        local_path = certificate_local_path_from_url(certificate.url)
        if local_path is not None:
            stale_paths.add(local_path)
        await session.delete(certificate)
        stats.certificates_deleted += 1
        changed = True

    return changed


def _legacy_category_candidates(remote_name: str) -> tuple[str, ...]:
    return LEGACY_CATEGORY_NAMES.get(_category_name_key(remote_name), ())


async def _sync_categories(
    session: AsyncSession,
    categories: list[WebsiteCatalogCategory] | None,
    products: list[Product],
    stats: WebsiteCatalogSyncStats,
) -> bool:
    if categories is None:
        return False

    existing_categories = list((
        await session.execute(select(ProductCategory))
    ).scalars().all())
    existing_links = list((
        await session.execute(select(ProductByCategory))
    ).scalars().all())
    categories_by_source_id = {
        category.website_category_id: category
        for category in existing_categories
        if category.website_category_id is not None
    }
    available_by_name: dict[str, list[ProductCategory]] = {}
    for category in existing_categories:
        available_by_name.setdefault(_category_name_key(category.name), []).append(category)

    assignments: list[tuple[WebsiteCatalogCategory, ProductCategory]] = []
    assigned_category_ids: set[int] = set()
    for remote in categories:
        category = categories_by_source_id.get(remote.source_id)
        if category is not None and category.id in assigned_category_ids:
            raise ValueError("A local category is assigned to more than one Bitrix category")
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
                if category is not None:
                    break
        if category is None:
            category = ProductCategory(
                name=f"__bitrix_category_{remote.source_id}",
                description=None,
                archived=False,
                website_category_id=remote.source_id,
            )
            session.add(category)
            await session.flush()
            existing_categories.append(category)
            stats.categories_created += 1
        else:
            stats.categories_matched += 1
        assigned_category_ids.add(category.id)
        assignments.append((remote, category))

    renamed_assignments = [
        (remote, category)
        for remote, category in assignments
        if category.name != remote.name
    ]
    for remote, category in renamed_assignments:
        category.name = f"__bitrix_category_{remote.source_id}_{category.id}"
    if renamed_assignments:
        await session.flush()

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
        if category.id in assigned_category_ids or category.archived:
            continue
        category.archived = True
        stats.categories_archived += 1
        changed = True

    await session.flush()
    products_by_system_id = {
        product.system_id: product
        for product in products
        if product.system_id is not None
    }
    category_by_source_id = {
        remote.source_id: category
        for remote, category in assignments
    }
    desired_pairs: set[tuple[int, int]] = set()
    for remote in categories:
        category = category_by_source_id[remote.source_id]
        for system_id in remote.product_system_ids:
            product = products_by_system_id.get(system_id)
            if product is None:
                stats.category_links_skipped_missing_products += 1
                continue
            desired_pairs.add((product.id, category.id))

    existing_by_pair = {
        (link.product_id, link.category_id): link
        for link in existing_links
    }
    for pair, link in existing_by_pair.items():
        if pair in desired_pairs:
            continue
        await session.delete(link)
        stats.category_links_deleted += 1
        changed = True
    for product_id, category_id in desired_pairs:
        if (product_id, category_id) in existing_by_pair:
            continue
        session.add(ProductByCategory(
            product_id=product_id,
            category_id=category_id,
        ))
        stats.category_links_created += 1
        changed = True

    return changed


async def sync_catalog_content_with_website(
    session: AsyncSession,
    *,
    client: WebsiteCatalogSyncClient | None = None,
) -> WebsiteCatalogSyncStats:
    sync_client = client or WebsiteCatalogSyncClient()
    stats = WebsiteCatalogSyncStats()
    payload = await sync_client.pull()
    contents = _parse_content_rows(
        payload,
        stats,
        public_base_url=sync_client.public_base_url,
    )
    categories = _parse_categories(payload, stats)
    if not contents:
        return stats

    products = list((
        await session.execute(
            select(Product).options(selectinload(Product.certificates))
        )
    ).scalars().all())
    certificates_changed = False
    downloaded_paths: set[Path] = set()
    stale_paths: set[Path] = set()
    try:
        async with httpx.AsyncClient(
            timeout=sync_client.timeout,
            transport=sync_client.transport,
            follow_redirects=False,
        ) as download_client:
            for product, content in _match_content_rows(products, contents, stats):
                if _apply_content(product, content, stats):
                    stats.updated_products += 1
                else:
                    stats.unchanged += 1
                if await _apply_certificates(
                    session,
                    product,
                    content.certificates,
                    stats,
                    download_client=download_client,
                    downloaded_paths=downloaded_paths,
                    stale_paths=stale_paths,
                ):
                    certificates_changed = True

        categories_changed = await _sync_categories(
            session,
            categories,
            products,
            stats,
        )

        changed = bool(
            stats.updated_products
            or certificates_changed
            or categories_changed
        )
        if changed:
            await session.commit()
    except Exception:
        await session.rollback()
        raise

    for stale_path in stale_paths - downloaded_paths:
        if remove_local_certificate(stale_path):
            stats.certificate_files_deleted += 1

    if changed:
        cache = get_cache_service()
        await cache.bump_namespace("catalog")
        await cache.bump_namespace("product")
        if categories_changed:
            await cache.bump_namespace("categories")
    return stats
