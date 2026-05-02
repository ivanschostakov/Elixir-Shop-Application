from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.app.modules.product_categories.router as product_categories_router_module
from src.app.main import app
from src.database import get_db


class FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    async def versioned_key(self, namespace: str, base_key: str) -> str:
        return f"{namespace}:{base_key}"

    async def get_json(self, key: str, *, key_prefix: str):
        return self.store.get(key)

    async def set_json(self, key: str, value, *, ttl_seconds: int, key_prefix: str):
        self.store[key] = value


def _category(category_id: int, name: str):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=category_id,
        name=name,
        description=None,
        created_at=now,
        updated_at=now,
    )


def test_product_categories_endpoint_uses_cache(monkeypatch: pytest.MonkeyPatch):
    calls = {"count": 0}
    fake_cache = FakeCache()

    async def fake_get_db():
        yield object()

    async def fake_get_product_categories(*args, **kwargs):
        calls["count"] += 1
        return [_category(1, "Category A"), _category(2, "Category B")]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(product_categories_router_module, "get_product_categories", fake_get_product_categories)
    monkeypatch.setattr(product_categories_router_module, "get_cache_service", lambda: fake_cache)

    try:
        with TestClient(app) as test_client:
            first = test_client.get("/api/v1/product-categories")
            second = test_client.get("/api/v1/product-categories")

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json() == second.json()
        assert calls["count"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
