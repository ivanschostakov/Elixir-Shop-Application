import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.app.services.community as community_service
import src.app.services.telegram_updates as telegram_updates_service
from src.database.schemas.community import CommunityAuthorRead, CommunityMessageRead


def test_community_response_does_not_expose_telegram_username():
    payload = CommunityMessageRead(
        id=10,
        topic_id=3,
        author=CommunityAuthorRead(id=7, full_name="Ada Lovelace", avatar_url="https://example.test/avatar", is_current_user=False),
        text="Hello",
        attachments=[],
        reply_to=None,
        unsupported_type=None,
        telegram_url=None,
        delivery_status="sent",
        created_at=datetime.now(timezone.utc),
    ).model_dump()

    assert payload["author"]["full_name"] == "Ada Lovelace"
    assert payload["author"]["avatar_url"]
    assert "username" not in payload["author"]
    assert "telegram_user_id" not in payload["author"]


def test_active_member_statuses():
    assert community_service._is_active_member({"status": "creator"}) is True
    assert community_service._is_active_member({"status": "administrator"}) is True
    assert community_service._is_active_member({"status": "member"}) is True
    assert community_service._is_active_member({"status": "restricted", "is_member": True}) is True
    assert community_service._is_active_member({"status": "restricted", "is_member": False}) is False
    assert community_service._is_active_member({"status": "left"}) is False
    assert community_service._is_active_member({"status": "kicked"}) is False


def test_membership_access_uses_telegram_and_redis_cache(monkeypatch):
    class FakeTelegramClient:
        calls = 0

        async def get_chat_member(self, chat_id, user_id):
            self.calls += 1
            return {"status": "member"}

    fake_client = FakeTelegramClient()
    cached_values = {}

    class FakeCache:
        client = object()

        async def get_json(self, key, **_kwargs):
            return cached_values.get(key)

        async def set_json(self, key, value, **_kwargs):
            cached_values[key] = value

    user = SimpleNamespace(telegram_user_id=12345)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(community_service, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(community_service, "get_cache_service", lambda: FakeCache())

    first = asyncio.run(community_service._membership_access(user, telegram_client=fake_client))
    second = asyncio.run(community_service._membership_access(user, telegram_client=fake_client))

    assert first == "granted"
    assert second == "granted"
    assert fake_client.calls == 1


def test_membership_access_gates_unlinked_nonmember_and_unavailable(monkeypatch):
    class NoCache:
        client = None

        async def set_json(self, *_args, **_kwargs):
            return None

    class FakeTelegramClient:
        def __init__(self, result=None, error=None):
            self.result = result
            self.error = error

        async def get_chat_member(self, _chat_id, _user_id):
            if self.error:
                raise self.error
            return self.result

    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(community_service, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(community_service, "get_cache_service", lambda: NoCache())

    assert asyncio.run(community_service._membership_access(SimpleNamespace(telegram_user_id=None))) == "telegram_link_required"
    assert asyncio.run(community_service._membership_access(SimpleNamespace(telegram_user_id=5), telegram_client=FakeTelegramClient({"status": "left"}))) == "membership_required"
    assert asyncio.run(community_service._membership_access(SimpleNamespace(telegram_user_id=6), telegram_client=FakeTelegramClient(error=TimeoutError()))) == "temporarily_unavailable"


def test_media_signatures_are_user_scoped(monkeypatch):
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET", "test-secret")
    expires = 4102444800
    signature = community_service._media_signature(media_type="attachment", media_id=8, user_id=12, expires=expires)

    assert community_service.verify_community_media_signature(media_type="attachment", media_id=8, user_id=12, expires=expires, signature=signature)
    assert not community_service.verify_community_media_signature(media_type="attachment", media_id=8, user_id=13, expires=expires, signature=signature)


def test_community_update_delivery_marker_joins_message_transaction(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeSession:
        async def commit(self):
            calls.append(("commit", None))

    async def fake_register(_db, **kwargs):
        calls.append(("register", kwargs.get("commit")))
        return True

    async def fake_process(_db, _payload):
        calls.append(("process", None))
        return {"ok": True}

    monkeypatch.setattr(telegram_updates_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(telegram_updates_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(telegram_updates_service, "register_webhook_delivery", fake_register)
    monkeypatch.setattr(telegram_updates_service, "process_community_telegram_message", fake_process)

    result = asyncio.run(telegram_updates_service.process_telegram_update(
        FakeSession(),
        {"update_id": 22, "message": {"message_id": 8, "chat": {"id": -10099}}},
    ))

    assert result == {"ok": True}
    assert calls == [("register", False), ("process", None), ("commit", None)]


def test_outbound_worker_is_inert_when_feature_disabled(monkeypatch):
    class SessionThatMustNotBeUsed:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("disabled bridge queried the outbound queue")

    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", False)

    assert asyncio.run(community_service.relay_next_community_message(SessionThatMustNotBeUsed())) is False


def test_long_telegram_text_is_split_without_losing_content():
    text = "Header\n\n" + ("message " * 900)

    chunks = community_service._telegram_text_chunks(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())
