from types import SimpleNamespace
from unittest.mock import AsyncMock

import config
import pytest
from fastapi import HTTPException, Request

from src.app.modules.users.me import companion
from src.app.modules.users.me.community import require_community_access
from src.app.services.app_integrity import service as integrity
from src.app.services.platform_availability import allow_push_for_platform, skip_ios_app_attest


@pytest.fixture()
def users(monkeypatch):
    monkeypatch.setattr(config, "IOS_PRIVATE_FEATURES_USER_ID", 42)
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "APPLE_DEV_MODE", False)
    return (
        SimpleNamespace(id=42, username="private", is_active=True, is_verified=True),
        SimpleNamespace(id=43, username="admin", is_active=True, is_verified=True),
    )


def request(platform, proof_platform=None, method="GET"):
    headers = [(b"x-app-platform", platform.encode())]
    if proof_platform:
        headers.append((b"x-app-integrity-platform", proof_platform.encode()))
    return Request({"type": "http", "path": "/test", "method": method, "headers": headers})


@pytest.mark.anyio
async def test_ios_private_feature_routes(users, monkeypatch):
    privileged, regular = users
    verify = AsyncMock()
    monkeypatch.setattr(companion, "verify_app_integrity_request", verify)
    monkeypatch.setattr(companion, "ensure_app_ai_access", AsyncMock())
    ios = request("ios")
    assert (await companion.availability(ios, user=regular))["available"] is False
    assert (await companion.availability(ios, user=privileged))["available"] is True
    with pytest.raises(HTTPException) as err:
        await companion.native_access(ios, db=None, user=regular)
    assert err.value.status_code == 403
    with pytest.raises(HTTPException):
        await require_community_access(request("android", "ios"), user=regular)
    with pytest.raises(HTTPException) as err:
        await require_community_access(ios, user=regular)
    assert err.value.status_code == 403
    verify.assert_not_awaited()
    assert await companion.native_access(ios, db=None, user=privileged) is privileged
    await require_community_access(ios, user=privileged)
    android = request("android", "android")
    assert (await companion.availability(android, user=regular))["available"] is True
    assert await companion.native_access(android, db=None, user=regular) is regular
    await require_community_access(android, user=regular)


@pytest.mark.anyio
async def test_attest_exception_uses_authenticated_id_not_username_or_platform_header_alone(users):
    privileged, regular = users
    await integrity.verify_app_integrity_request(request("ios"), action="ai-companion", current_user=privileged, force_enforce=True)
    for req, user in [
        (request("ios"), regular), (request("ios"), None),
        (request("android", "android"), privileged), (request("ios", "android"), privileged),
    ]:
        assert not skip_ios_app_attest(req.headers, user)
        with pytest.raises(HTTPException) as error:
            await integrity.verify_app_integrity_request(req, action="ai-companion", current_user=user, force_enforce=True)
        assert error.value.status_code == 403
    privileged.is_active = False
    assert not skip_ios_app_attest(request("ios").headers, privileged)


def test_feature_notifications_do_not_leak_to_other_ios_users(users):
    privileged, regular = users
    for kind in ("ai_companion", "ai_companion_supply", "community_message"):
        assert not allow_push_for_platform("ios", {"type": kind}, user_id=regular.id)
        assert allow_push_for_platform("ios", {"type": kind}, user_id=privileged.id)
        assert allow_push_for_platform("android", {"type": kind}, user_id=regular.id)
    assert allow_push_for_platform("ios", {"type": "order_status_changed"}, user_id=regular.id)
