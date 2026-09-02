from types import SimpleNamespace
from unittest.mock import AsyncMock

import config
import pytest

from src.app.services.platform_availability import allow_push_for_platform, catalog_response, is_commerce_blocked, is_commerce_path
from src.app.services.push_notifications import _build_push_messages


@pytest.mark.parametrize("path,method", [
    ("/api/v1/products", "GET"), ("/api/v1/products/123/", "GET"),
    ("/api/v1/product-categories", "GET"), ("/api/v1/banners", "GET"),
    ("/api/v1/guest/orders", "POST"), ("/api/v1/users/me/basket/items", "POST"),
    ("/api/v1/users/me/order-drafts", "GET"), ("/api/v1/users/me/recommendations", "GET"),
    ("/api/v1/users/me/favorites/products", "GET"), ("/api/v1/users/me/stock-subscriptions/products", "POST"),
    ("/api/v1/users/me/orders", "POST"), ("/api/v1/users/me/orders/42/repeat", "POST"),
])
def test_block_ios_only(monkeypatch, path, method):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    assert is_commerce_blocked({"x-app-platform": "ios"}, path, method)
    for platform in ("android", "web"):
        assert not is_commerce_blocked({"x-app-platform": platform}, path, method)
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    assert not is_commerce_blocked({"x-app-platform": "ios"}, path, method)


@pytest.mark.parametrize("path", [
    "/api/v1/admin/products", "/api/v1/auth/login", "/api/v1/app-version",
    "/api/v1/users/me/support", "/api/v1/users/me/ai-chat", "/api/v1/users/me/community/topics",
    "/api/v1/users/me/orders/42", "/api/v1/users/me/orders", "/api/v1/delivery/cdek/delivery-point-markers",
    "/api/v1/products-extra", "/api/v1/payments/status",
    "/api/v1/users/me/benefits/check",
])
def test_keep_other_features(path):
    assert not is_commerce_path(path)


def test_web_on_iphone_is_not_native_ios(monkeypatch):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    assert not is_commerce_blocked({"x-app-platform": "web", "user-agent": "iPhone Safari"}, "/api/v1/products", "GET")
    assert is_commerce_blocked({"user-agent": "Elixir iPhone"}, "/api/v1/products", "GET")


def test_policy_and_middleware(client, monkeypatch):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    policy = client.get("/api/v1/app-version").json()
    assert policy["apple_dev_mode"] is True
    result = client.get("/api/v1/products/123", headers={"X-App-Platform": "ios"})
    assert result.status_code == 404
    assert result.json()["detail"] == "Not found"
    assert result.headers["cache-control"] == "no-store"
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    assert client.get("/api/v1/app-version").json()["apple_dev_mode"] is False


@pytest.mark.parametrize("path", [
    "/api/v1/products", "/api/v1/products/?q=test&limit=1", "/api/v1/product-categories",
    "/api/v1/banners", "/api/v1/products/123/similar", "/api/v1/products/123/reviews",
    "/api/v1/favorites/products", "/api/v1/users/me/favorites/products",
    "/api/v1/users/me/recommendations", "/api/v1/users/me/promotions",
    "/api/v1/users/me/order-drafts", "/api/v1/users/me/search-queries",
])
def test_ios_lists_are_successful_empty_arrays(client, monkeypatch, path):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    result = client.get(path, headers={"X-App-Platform": "ios"})
    assert result.status_code == 200
    assert result.json() == []
    assert result.headers["cache-control"] == "no-store"
    assert "X-App-Platform" in result.headers["vary"]
    assert catalog_response({"x-app-platform": "android"}, path.split("?")[0], "GET") is None
    assert catalog_response({"x-app-platform": "web", "user-agent": "iPhone"}, path.split("?")[0], "GET") is None
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    assert catalog_response({"x-app-platform": "ios"}, path.split("?")[0], "GET") is None


def test_empty_collection_keeps_its_envelope(client, monkeypatch):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    result = client.get("/api/v1/products/123/questions", headers={"X-App-Platform": "ios"})
    assert result.status_code == 200
    assert result.json() == {"items": [], "total": 0}


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_basket_view_is_empty_without_clearing_stored_items(client, monkeypatch, method):
    from src.app.main import app
    from src.app.modules.auth.dependencies import get_current_user
    from src.app.modules.users.me import basket as basket_module
    from src.database import get_db

    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    db = SimpleNamespace(commit=AsyncMock(), delete=AsyncMock())
    async def fake_db():
        yield db
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7)
    now = config.ufa_now()
    stored = SimpleNamespace(id=42, created_at=now, updated_at=now, items=[{"variant_id": 9, "quantity": 2}])
    read = AsyncMock(return_value=stored)
    monkeypatch.setattr(basket_module, "get_basket_by_user_id", read)
    pricing = AsyncMock(side_effect=AssertionError("Empty view must not sync promos or prices"))
    monkeypatch.setattr(basket_module, "refresh_assigned_referrer_promo", pricing)
    result = client.request(method, "/api/v1/users/me/basket", headers={"X-App-Platform": "ios"})
    assert result.status_code == 200
    data = result.json()
    assert (data["id"], data["user_id"], data["items"]) == (42, 7, [])
    assert data["items_count"] == data["total_quantity"] == 0
    assert float(data["total_amount"]) == float(data["grand_total"]) == float(data["delivery_total"]) == 0
    assert stored.items == [{"variant_id": 9, "quantity": 2}]
    read.assert_awaited_once_with(db, 7)
    db.commit.assert_not_awaited()
    db.delete.assert_not_awaited()
    pricing.assert_not_awaited()


def test_guest_basket_quote_is_empty_even_for_cached_items(client, monkeypatch):
    from src.app.main import app
    from src.app.modules.guest import router as guest_module
    from src.database import get_db

    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    async def fake_db():
        yield SimpleNamespace()
    app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(guest_module, "_guest_rate_limit", AsyncMock())
    pricing = AsyncMock(side_effect=AssertionError("Must not quote cached products"))
    monkeypatch.setattr(guest_module, "quote_guest_basket", pricing)
    result = client.post("/api/v1/guest/basket/quote", headers={"X-App-Platform": "ios"}, json={"items": [{"variant_id": 9, "quantity": 2}]})
    assert result.status_code == 200
    assert result.json()["items"] == []
    assert float(result.json()["grand_total"]) == 0
    pricing.assert_not_awaited()


def test_writes_are_not_acknowledged_as_successful_empty_lists(client, monkeypatch):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    for path in ("/api/v1/users/me/orders", "/api/v1/guest/orders", "/api/v1/users/me/basket/items"):
        result = client.post(path, headers={"X-App-Platform": "ios"}, json={})
        assert result.status_code == 403
        assert result.json()["detail"]["code"] == "ios_catalog_unavailable"
    assert catalog_response({"x-app-platform": "ios"}, "/api/v1/products", "OPTIONS") is None


def test_marketing_push_is_filtered_per_device(monkeypatch):
    monkeypatch.setattr(config, "APPLE_DEV_MODE", True)
    tokens = [SimpleNamespace(platform=platform, expo_push_token=platform) for platform in ("ios", "android")]
    messages = _build_push_messages(tokens, title="Sale", body="Promo", data={"type": "campaign"})
    assert [message["to"] for message in messages] == ["android"]
    assert not allow_push_for_platform("ios", {})
    for kind in ("support_reply", "order_status_changed"):
        assert allow_push_for_platform("ios", {"type": kind})
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    assert allow_push_for_platform("ios", {"type": "campaign"})
