from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request

import config
from src.app.modules.users.me import companion
from src.app.services.ai.chat import send_user_chat_message
from src.app.services.app_integrity.common import ios_allowed_environments


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("name", [
    "AI_COMPANION_ENABLED", "AI_COMPANION_DIALOGUE_ENABLED", "TELEGRAM_COMMUNITY_ENABLED",
    "TELEGRAM_USERBOT_ENABLED", "MOY_SKLAD_ORDER_SYNC_ENABLED",
    "LOYALTY_USE_SETTLEMENT_BALANCE", "LOYALTY_SETTLEMENT_CHECKOUT_ENABLED",
])
def test_release_features_are_fixed_on(name, monkeypatch):
    monkeypatch.setenv(name, "false")
    assert getattr(config, name) is True


def test_production_attestations_are_the_only_accepted_environment(monkeypatch):
    monkeypatch.setenv("APP_INTEGRITY_IOS_ALLOWED_ENVIRONMENTS", "production,development,sandbox")
    assert ios_allowed_environments() == {"production"}


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", [None, 0, 1, 3])
async def test_old_mentor_messages_require_an_updated_client(protocol):
    db = SimpleNamespace(commit=AsyncMock(), execute=AsyncMock())
    request = Request({"type": "http", "path": "/test", "headers": []})
    with pytest.raises(HTTPException) as error:
        await companion.message(request, text="hello", client_request_id="test-request-001", attachments=None,
                                dialogue_protocol=protocol, user=SimpleNamespace(id=7), db=db)
    assert error.value.status_code == 426
    assert error.value.detail["code"] == "mentor_client_update_required"
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_old_mentor_format_is_also_rejected_at_the_shared_service():
    with pytest.raises(HTTPException) as error:
        await send_user_chat_message(None, user=SimpleNamespace(id=7), text="hello", attachments=None,
                                     professor_client=None, companion_profile=SimpleNamespace(id=9), dialogue_protocol=1)
    assert error.value.status_code == 426


def test_consent_version_is_fixed_even_if_environment_requests_another_version(monkeypatch):
    monkeypatch.setenv("AI_COMPANION_CONSENT_VERSION", "different-version")
    assert config.AI_COMPANION_CONSENT_VERSION == "companion-v1"
