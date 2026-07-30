import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from src.integrations.website_catalog import (
    WebsiteCatalogContent,
    WebsiteCatalogSyncClient,
    WebsiteCatalogSyncStats,
    _apply_content,
    _parse_content_rows,
)


@pytest.mark.anyio
async def test_catalog_sync_client_signs_pull_request():
    secret = "catalog-secret-" * 4

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert json.loads(request.content) == {"action": "pull"}
        timestamp = request.headers["X-Elixir-Timestamp"]
        expected = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + request.content,
            hashlib.sha256,
        ).hexdigest()
        assert request.headers["X-Elixir-Signature"] == expected
        return httpx.Response(200, json={"ok": True, "products": [], "total": 0})

    client = WebsiteCatalogSyncClient(
        endpoint="https://example.test/bitrix/tools/elixir.catalogsync/sync.php",
        secret=secret,
        transport=httpx.MockTransport(handler),
    )

    result = await client.pull()

    assert result["products"] == []
    assert result["total"] == 0


def test_parse_content_rows_rejects_duplicate_and_invalid_ids():
    product_id = "7e2a5eeb-13e1-11f1-0a80-176100294e52"
    stats = WebsiteCatalogSyncStats()

    parsed = _parse_content_rows(
        {
            "products": [
                {
                    "system_id": product_id,
                    "description": "<p>Описание</p>",
                    "usage": None,
                    "storage": "<p>Хранение</p>",
                },
                {
                    "system_id": product_id,
                    "description": "<p>Дубликат</p>",
                    "usage": None,
                    "storage": None,
                },
                {
                    "system_id": "legacy-id",
                    "description": None,
                    "usage": None,
                    "storage": None,
                },
            ]
        },
        stats,
    )

    assert parsed == {}
    assert stats.fetched == 3
    assert stats.skipped_duplicate_system_id == 1
    assert stats.skipped_invalid_system_id == 1


def test_catalog_sync_client_rejects_insecure_configuration():
    with pytest.raises(RuntimeError, match="HTTPS"):
        WebsiteCatalogSyncClient(
            endpoint="http://example.test/sync.php",
            secret="catalog-secret-" * 4,
        )
    with pytest.raises(RuntimeError, match="32 characters"):
        WebsiteCatalogSyncClient(
            endpoint="https://example.test/sync.php",
            secret="short",
        )


def test_apply_content_maps_storage_to_expiration_and_clears_empty_fields():
    product = SimpleNamespace(
        description="<p>Старое описание</p>",
        usage="<p>Старое применение</p>",
        expiration="<p>Старое хранение</p>",
    )
    stats = WebsiteCatalogSyncStats()
    content = WebsiteCatalogContent(
        system_id=UUID("7e2a5eeb-13e1-11f1-0a80-176100294e52"),
        description="<p>Новое описание</p>",
        usage=None,
        storage="<p>Новое хранение</p>",
    )

    changed = _apply_content(product, content, stats)

    assert changed is True
    assert product.description == "<p>Новое описание</p>"
    assert product.usage is None
    assert product.expiration == "<p>Новое хранение</p>"
    assert stats.updated_description == 1
    assert stats.updated_usage == 1
    assert stats.updated_storage == 1
