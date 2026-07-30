from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    WEBSITE_CATALOG_SYNC_ENDPOINT,
    WEBSITE_CATALOG_SYNC_SECRET,
    WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS,
)
from src.app.services.cache import get_cache_service
from src.database.models import Product
from src.normalize import coerce_uuid


log = logging.getLogger("integrations.website_catalog")
MAX_PRODUCTS = 500
MAX_CONTENT_LENGTH = 200_000


@dataclass
class WebsiteCatalogSyncStats:
    fetched: int = 0
    matched: int = 0
    updated_products: int = 0
    updated_description: int = 0
    updated_usage: int = 0
    updated_storage: int = 0
    unchanged: int = 0
    skipped_invalid_system_id: int = 0
    skipped_duplicate_system_id: int = 0
    skipped_missing_product: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class WebsiteCatalogContent:
    system_id: UUID
    description: str | None
    usage: str | None
    storage: str | None


def website_catalog_sync_configured() -> bool:
    return bool(WEBSITE_CATALOG_SYNC_ENDPOINT and WEBSITE_CATALOG_SYNC_SECRET)


class WebsiteCatalogSyncClient:
    def __init__(
        self,
        *,
        endpoint: str | None = WEBSITE_CATALOG_SYNC_ENDPOINT,
        secret: str | None = WEBSITE_CATALOG_SYNC_SECRET,
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
        if len(secret) < 32:
            raise RuntimeError("Website catalog sync secret must contain at least 32 characters")
        self.endpoint = endpoint
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


def _parse_content_rows(
    payload: dict[str, Any],
    stats: WebsiteCatalogSyncStats,
) -> dict[UUID, WebsiteCatalogContent]:
    raw_products = payload.get("products")
    if not isinstance(raw_products, list):
        raise ValueError("Catalog sync response does not contain a product list")
    if len(raw_products) > MAX_PRODUCTS:
        raise ValueError("Catalog sync response contains too many products")

    stats.fetched = len(raw_products)
    parsed: dict[UUID, WebsiteCatalogContent] = {}
    duplicates: set[UUID] = set()
    for row in raw_products:
        if not isinstance(row, dict):
            stats.skipped_invalid_system_id += 1
            continue
        system_id = coerce_uuid(row.get("system_id"))
        if system_id is None:
            stats.skipped_invalid_system_id += 1
            continue
        if system_id in parsed:
            duplicates.add(system_id)
            continue
        parsed[system_id] = WebsiteCatalogContent(
            system_id=system_id,
            description=_content(row.get("description")),
            usage=_content(row.get("usage")),
            storage=_content(row.get("storage")),
        )

    for system_id in duplicates:
        parsed.pop(system_id, None)
    stats.skipped_duplicate_system_id = len(duplicates)
    return parsed


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


async def sync_catalog_content_with_website(
    session: AsyncSession,
    *,
    client: WebsiteCatalogSyncClient | None = None,
) -> WebsiteCatalogSyncStats:
    sync_client = client or WebsiteCatalogSyncClient()
    stats = WebsiteCatalogSyncStats()
    remote_by_system_id = _parse_content_rows(await sync_client.pull(), stats)
    if not remote_by_system_id:
        return stats

    products = list((
        await session.execute(
            select(Product).where(Product.system_id.in_(remote_by_system_id))
        )
    ).scalars().all())
    local_by_system_id = {
        product.system_id: product
        for product in products
        if product.system_id is not None
    }
    stats.matched = len(local_by_system_id)
    stats.skipped_missing_product = len(remote_by_system_id) - stats.matched

    for system_id, content in remote_by_system_id.items():
        product = local_by_system_id.get(system_id)
        if product is None:
            continue
        if _apply_content(product, content, stats):
            stats.updated_products += 1
        else:
            stats.unchanged += 1

    if stats.updated_products:
        await session.commit()
        cache = get_cache_service()
        await cache.bump_namespace("catalog")
        await cache.bump_namespace("product")
    return stats
