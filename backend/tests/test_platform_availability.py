from types import SimpleNamespace

import config
import pytest
from fastapi import Request

from src.app.modules.products.access import get_catalog_scope
from src.app.services.catalog_access import purchase_category_scope
from src.app.services.platform_availability import is_ios_request
from src.app.services.push_notifications import _build_push_messages


@pytest.fixture()
def anyio_backend():
    return "asyncio"


def test_native_platform_detection_respects_explicit_web_clients():
    assert is_ios_request({"x-app-platform": "ios"})
    assert is_ios_request({"x-app-integrity-platform": "ios"})
    assert is_ios_request({"user-agent": "Elixir iPhone"})
    assert not is_ios_request({"x-app-platform": "web", "user-agent": "iPhone Safari"})
    assert not is_ios_request({"x-app-platform": "android"})


@pytest.mark.anyio
async def test_full_catalog_and_checkout_are_identical_for_all_customers_and_platforms():
    for platform in ("ios", "android", "web"):
        req = Request({"type": "http", "path": "/test", "headers": [(b"x-app-platform", platform.encode())]})
        for user in (None, SimpleNamespace(id=42), SimpleNamespace(id=43)):
            assert await get_catalog_scope(req, current_user=user) is None
            assert purchase_category_scope(user.id if user else None, client_platform=platform) is None


def test_feature_pushes_do_not_depend_on_a_special_account():
    tokens = [SimpleNamespace(platform=platform, expo_push_token=f"{platform}-{uid}", user_id=uid)
              for platform in ("ios", "android") for uid in (42, 43)]
    for kind in ("community_message", "ai_companion", "support_reply", "order_status_changed"):
        messages = _build_push_messages(tokens, title="Test", body="Test", data={"type": kind})
        assert {message["to"] for message in messages} == {token.expo_push_token for token in tokens}
