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
    _legacy_category_candidates,
    _match_content_rows,
    _parse_categories,
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
        endpoint="https://example.test:8443/bitrix/tools/elixir.catalogsync/sync.php",
        secret=secret,
        transport=httpx.MockTransport(handler),
    )

    result = await client.pull()

    assert result["products"] == []
    assert result["total"] == 0
    assert client.public_base_url == "https://example.test/"


def test_parse_content_rows_rejects_duplicate_and_invalid_ids():
    product_id = "7e2a5eeb-13e1-11f1-0a80-176100294e52"
    stats = WebsiteCatalogSyncStats()

    parsed = _parse_content_rows(
        {
            "products": [
                {
                    "system_id": product_id,
                    "sku": "00-00000123",
                    "description": "<p>Описание</p>",
                    "usage": None,
                    "storage": "<p>Хранение</p>",
                },
                {
                    "system_id": product_id,
                    "sku": "00-00000123",
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

    assert parsed == []
    assert stats.fetched == 3
    assert stats.skipped_duplicate_system_id == 1
    assert stats.skipped_invalid_system_id == 1


def test_catalog_content_matches_unique_sku_when_moysklad_ids_differ():
    product = SimpleNamespace(
        id=1,
        system_id=UUID("7e2a5eeb-13e1-11f1-0a80-176100294e52"),
        sku="00-00000123",
    )
    content = WebsiteCatalogContent(
        system_id=UUID("1b2321a8-597f-11f0-9098-fa163e347889"),
        sku="00-00000123",
        description="<p>Описание</p>",
        usage=None,
        storage=None,
    )
    stats = WebsiteCatalogSyncStats()

    matched = _match_content_rows([product], [content], stats)

    assert matched == [(product, content)]
    assert stats.matched == 1
    assert stats.matched_by_system_id == 0
    assert stats.matched_by_sku == 1


def test_parse_content_rows_keeps_legacy_bitrix_id_with_sku():
    stats = WebsiteCatalogSyncStats()

    parsed = _parse_content_rows(
        {
            "products": [{
                "system_id": "duplicate_3965_legacy-id",
                "sku": "00-00000109",
                "description": "<p>Описание</p>",
                "usage": None,
                "storage": None,
            }]
        },
        stats,
    )

    assert len(parsed) == 1
    assert parsed[0].system_id is None
    assert parsed[0].sku == "00-00000109"
    assert stats.skipped_invalid_system_id == 0


def test_catalog_content_rejects_ambiguous_sku_fallback():
    contents = [
        WebsiteCatalogContent(
            system_id=None,
            sku="00-00000123",
            description=None,
            usage=None,
            storage=None,
        ),
    ]
    products = [
        SimpleNamespace(id=1, system_id=UUID(int=1), sku="00-00000123"),
        SimpleNamespace(id=2, system_id=UUID(int=2), sku="00-00000123"),
    ]
    stats = WebsiteCatalogSyncStats()

    assert _match_content_rows(products, contents, stats) == []
    assert stats.matched == 0
    assert stats.skipped_ambiguous_sku == 1


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
    with pytest.raises(RuntimeError, match="public base URL"):
        WebsiteCatalogSyncClient(
            endpoint="https://example.test/sync.php",
            secret="catalog-secret-" * 4,
            public_base_url="https://example.test/files",
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
        sku="00-00000123",
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


def test_parse_catalog_categories_and_product_certificates():
    product_id = "7e2a5eeb-13e1-11f1-0a80-176100294e52"
    stats = WebsiteCatalogSyncStats()
    payload = {
        "products": [{
            "system_id": product_id,
            "sku": "00-00000123",
            "description": None,
            "usage": None,
            "storage": None,
            "certificates": [{
                "source_file_id": 7342,
                "title": "Сертификат соответствия",
                "original_name": "certificate.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
                "path": "/upload/iblock/aa/certificate.pdf",
            }],
        }],
        "categories": [{
            "source_id": 149,
            "name": "Все пептиды",
            "product_system_ids": [product_id, product_id],
        }],
    }

    products = _parse_content_rows(
        payload,
        stats,
        public_base_url="https://elixirpeptide.com/",
    )
    categories = _parse_categories(payload, stats)

    assert len(products) == 1
    assert products[0].certificates is not None
    assert products[0].certificates[0].url == (
        "https://elixirpeptide.com/upload/iblock/aa/certificate.pdf"
    )
    assert categories is not None
    assert len(categories) == 1
    assert categories[0].source_id == 149
    assert categories[0].name == "Все пептиды"
    assert categories[0].product_system_ids == (UUID(product_id),)
    assert stats.certificates_fetched == 1
    assert stats.categories_fetched == 1


def test_category_parser_rejects_duplicate_active_names():
    stats = WebsiteCatalogSyncStats()

    with pytest.raises(ValueError, match="names must be unique"):
        _parse_categories(
            {
                "categories": [
                    {"source_id": 1, "name": "Категория", "product_system_ids": []},
                    {"source_id": 2, "name": " категория ", "product_system_ids": []},
                ],
            },
            stats,
        )


def test_legacy_category_aliases_preserve_existing_icon_ids():
    assert _legacy_category_candidates("Все пептиды") == ("пептиды",)
    assert _legacy_category_candidates("Для иммунной системы") == (
        "для имунной системы",
    )
    assert _legacy_category_candidates("Антидепресанты") == (
        "антидепрессанты",
    )
