import importlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from src.app import main as app_main
from src.app.modules.products.access import get_catalog_scope
from src.database import get_db
from src.database.crud.catalog.banner import get_banners

router = importlib.import_module("src.app.modules.banners.router")


@pytest.mark.anyio
@pytest.mark.parametrize("universal_only", [False, True])
async def test_universal_filter_is_applied_before_pagination(universal_only):
    class CapturingSession:
        async def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    db = CapturingSession()
    assert await get_banners(db, limit=1, offset=2, universal_only=universal_only) == []
    compiled = db.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "banners.status" in sql and "banners.starts_at" in sql and "banners.ends_at" in sql
    assert "LIMIT" in sql and "OFFSET" in sql
    assert ("banners.audience_json @>" in sql) == universal_only
    assert ("banners.outer_link IS NULL" in sql) == universal_only
    if universal_only:
        assert {"catalog_scope": "all"} in compiled.params.values()
        assert "/discover?tab=products" in compiled.params.values()


@pytest.mark.parametrize("scope", [None, (4,), ()])
def test_banner_api_keeps_full_and_universal_caches_separate(client, monkeypatch, scope):
    cached = {}
    calls = []
    now = datetime.now(timezone.utc)

    class Cache:
        async def versioned_key(self, namespace, key):
            return namespace + ":" + key

        async def get_json(self, key, **kwargs):
            return cached.get(key)

        async def set_json(self, key, value, **kwargs):
            cached[key] = value

    async def fetch(db, **kwargs):
        calls.append(kwargs)
        welcome = SimpleNamespace(id=10, image_path="/media/banners/welcome.png", inner_link="/discover?tab=products", created_at=now, updated_at=now)
        product = SimpleNamespace(id=11, image_path="/media/banners/product.png", inner_link="/products/148", created_at=now, updated_at=now)
        return [welcome] if kwargs["universal_only"] else [welcome, product]

    async def fake_db():
        yield object()

    app_main.app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(router, "get_banners", fetch)
    monkeypatch.setattr(router, "get_cache_service", Cache)
    # Prime unrestricted cache first, then verify it cannot leak product banners.
    app_main.app.dependency_overrides[get_catalog_scope] = lambda: None
    assert len(client.get("/api/v1/banners").json()) == 2
    app_main.app.dependency_overrides[get_catalog_scope] = lambda: scope
    expected = [10, 11] if scope is None else [10]
    for _ in range(2):
        response = client.get("/api/v1/banners")
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()] == expected
    assert [call["universal_only"] for call in calls] == ([False] if scope is None else [False, True])
