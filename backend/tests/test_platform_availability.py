from types import SimpleNamespace

import config
import pytest

from src.app.services.platform_availability import allow_push_for_platform, is_commerce_blocked, is_commerce_path
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
    assert result.status_code == 403
    assert result.json()["detail"]["code"] == "ios_catalog_unavailable"
    assert result.headers["cache-control"] == "no-store"
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    assert client.get("/api/v1/app-version").json()["apple_dev_mode"] is False


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
