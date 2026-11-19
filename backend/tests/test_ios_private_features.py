from types import SimpleNamespace
from unittest.mock import AsyncMock

import config
import pytest
from fastapi import HTTPException, Request

from src.app.modules.users.me import companion
from src.app.services.app_integrity import service as integrity


pytestmark = pytest.mark.real_app_integrity

@pytest.fixture()
def anyio_backend():
    return "asyncio"


def request(platform, proof_platform=None):
    headers = [(b"x-app-platform", platform.encode())]
    if proof_platform:
        headers.append((b"x-app-integrity-platform", proof_platform.encode()))
    return Request({"type": "http", "path": "/test", "method": "GET", "headers": headers})


@pytest.mark.anyio
async def test_mentor_is_available_to_every_native_customer(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    verify = AsyncMock()
    monkeypatch.setattr(companion, "verify_app_integrity_request", verify)
    monkeypatch.setattr(companion, "ensure_app_ai_access", AsyncMock())
    for user_id in (42, 43):
        user = SimpleNamespace(id=user_id, is_active=True, is_verified=True)
        for platform in ("ios", "android"):
            req = request(platform, platform)
            assert (await companion.availability(req, user=user))["available"] is True
            assert await companion.native_access(req, db=None, user=user) is user
    assert verify.await_count == 4
    assert all(call.kwargs["action"] == "ai-companion" for call in verify.await_args_list)


@pytest.mark.anyio
async def test_no_customer_can_bypass_device_verification(monkeypatch):
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    for user_id in (42, 43):
        user = SimpleNamespace(id=user_id, is_active=True, is_verified=True)
        with pytest.raises(HTTPException) as error:
            await integrity.verify_app_integrity_request(
                request("ios", "ios"), action="ai-companion", current_user=user,
            )
        assert error.value.status_code == 403
        with pytest.raises(HTTPException) as error:
            await companion.native_access(request("ios"), db=None, user=user)
        assert error.value.status_code == 403
