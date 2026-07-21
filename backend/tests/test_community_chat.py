import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.app.services.community as community_service
import src.app.services.community_topics as community_topics_service
import src.app.services.telegram_updates as telegram_updates_service
import src.integrations.telegram.userbot as telegram_userbot
from src.app.services.community_topics import TelegramForumTopicSnapshot
from src.database.models import CommunityTopic
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
    assert payload["reactions"] == []
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


def test_app_community_access_does_not_call_telegram(monkeypatch):
    class FakeTelegramClient:
        calls = 0

        async def get_chat_member(self, chat_id, user_id):
            self.calls += 1
            return {"status": "member"}

    fake_client = FakeTelegramClient()
    user = SimpleNamespace(telegram_user_id=None)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(community_service, "TELEGRAM_BOT_TOKEN", "test-token")

    first = asyncio.run(community_service._membership_access(user, telegram_client=fake_client))
    second = asyncio.run(community_service._membership_access(user, telegram_client=fake_client))

    assert first == "granted"
    assert second == "granted"
    assert fake_client.calls == 0


def test_app_community_access_only_requires_bridge_configuration(monkeypatch):
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(community_service, "TELEGRAM_BOT_TOKEN", "test-token")
    assert asyncio.run(community_service._membership_access(SimpleNamespace(telegram_user_id=None))) == "granted"
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_ENABLED", False)
    assert asyncio.run(community_service._membership_access(SimpleNamespace(telegram_user_id=None))) == "temporarily_unavailable"


def test_media_signatures_are_user_scoped(monkeypatch):
    monkeypatch.setattr(community_service, "TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET", "test-secret")
    expires = 4102444800
    signature = community_service._media_signature(media_type="attachment", media_id=8, user_id=12, expires=expires)

    assert community_service.verify_community_media_signature(media_type="attachment", media_id=8, user_id=12, expires=expires, signature=signature)
    assert not community_service.verify_community_media_signature(media_type="attachment", media_id=8, user_id=13, expires=expires, signature=signature)


def test_community_reactions_are_aggregated_and_mark_the_current_user():
    message = SimpleNamespace(reactions=[
        SimpleNamespace(emoji="👍", user_id=12),
        SimpleNamespace(emoji="👍", user_id=13),
        SimpleNamespace(emoji="❤️", user_id=13),
    ])

    reactions = [item.model_dump() for item in community_service._serialize_reactions(message, user_id=12)]

    assert reactions == [
        {"emoji": "👍", "count": 2, "reacted_by_me": True},
        {"emoji": "❤️", "count": 1, "reacted_by_me": False},
    ]


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


def test_community_edited_update_joins_message_transaction(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeSession:
        async def commit(self):
            calls.append(("commit", None))

    async def fake_register(_db, **kwargs):
        calls.append(("register", kwargs.get("commit")))
        return True

    async def fake_process(_db, payload):
        calls.append(("process", "edited_message" in payload))
        return {"ok": True, "edited": True}

    monkeypatch.setattr(telegram_updates_service, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(telegram_updates_service, "TELEGRAM_COMMUNITY_CHAT_ID", -10099)
    monkeypatch.setattr(telegram_updates_service, "register_webhook_delivery", fake_register)
    monkeypatch.setattr(telegram_updates_service, "process_community_telegram_message", fake_process)

    result = asyncio.run(telegram_updates_service.process_telegram_update(
        FakeSession(),
        {"update_id": 23, "edited_message": {"message_id": 8, "chat": {"id": -10099}}},
    ))

    assert result == {"ok": True, "edited": True}
    assert calls == [("register", False), ("process", True), ("commit", None)]


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


def test_app_message_telegram_header_distinguishes_messages_and_replies():
    author = SimpleNamespace(full_name="Татьяна 🧪")
    message = SimpleNamespace(author=author, reply_to=None)
    reply = SimpleNamespace(author=author, reply_to=SimpleNamespace(id=12))

    author_name, message_header = community_service._telegram_app_header(message)
    _, reply_header = community_service._telegram_app_header(reply)

    assert message_header == "Татьяна 🧪 · 💬 Приложение"
    assert reply_header == "Татьяна 🧪 · ↩️ Приложение"
    assert community_service._telegram_author_entities(message_header, author_name) == [
        {"type": "bold", "offset": 0, "length": 10},
    ]


def test_authoritative_topic_snapshot_discovers_updates_restores_and_deletes():
    existing = [
        CommunityTopic(
            telegram_chat_id=-10099,
            telegram_thread_id=10,
            name="Old name",
            is_closed=False,
            is_hidden=False,
            is_pinned=False,
            is_deleted=False,
        ),
        CommunityTopic(
            telegram_chat_id=-10099,
            telegram_thread_id=20,
            name="Deleted topic",
            is_closed=False,
            is_hidden=False,
            is_pinned=False,
            is_deleted=False,
        ),
        CommunityTopic(
            telegram_chat_id=-10099,
            telegram_thread_id=30,
            name="Restored topic",
            is_closed=True,
            is_hidden=False,
            is_pinned=False,
            is_deleted=True,
        ),
    ]
    snapshots = [
        TelegramForumTopicSnapshot(
            thread_id=10,
            name="Renamed topic",
            icon_color=0x6FB9F0,
            is_closed=True,
            is_pinned=True,
            top_message_id=101,
        ),
        TelegramForumTopicSnapshot(thread_id=30, name="Restored topic"),
        TelegramForumTopicSnapshot(thread_id=40, name="New topic"),
    ]

    new_topics, result = community_topics_service.apply_telegram_topic_snapshots(
        existing,
        snapshots,
        chat_id=-10099,
        synced_at=datetime.now(timezone.utc),
    )

    by_thread = {topic.telegram_thread_id: topic for topic in [*existing, *new_topics]}
    assert result.discovered == 1
    assert result.restored == 1
    assert result.deleted == 1
    assert result.total == 3
    assert by_thread[10].name == "Renamed topic"
    assert by_thread[10].is_closed is True
    assert by_thread[10].is_pinned is True
    assert by_thread[10].telegram_top_message_id == 101
    assert by_thread[20].is_deleted is True
    assert by_thread[30].is_deleted is False
    assert by_thread[40].name == "New topic"


def test_empty_topic_snapshot_cannot_delete_existing_topics():
    existing = CommunityTopic(
        telegram_chat_id=-10099,
        telegram_thread_id=10,
        name="Keep me",
        is_deleted=False,
    )

    try:
        community_topics_service.apply_telegram_topic_snapshots(
            [existing],
            [],
            chat_id=-10099,
        )
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("an empty authoritative snapshot must be rejected")

    assert existing.is_deleted is False


def test_telethon_topic_snapshot_parses_structural_metadata():
    raw = SimpleNamespace(
        id=77,
        title="Product questions",
        icon_color=0xFFD67E,
        icon_emoji_id=987654321,
        closed=True,
        hidden=False,
        pinned=True,
        top_message=900,
        from_id=SimpleNamespace(user_id=123),
        date=datetime.now(timezone.utc),
    )

    snapshot = telegram_userbot._topic_snapshot(raw, get_peer_id=lambda peer: peer.user_id)

    assert snapshot is not None
    assert snapshot.thread_id == 77
    assert snapshot.name == "Product questions"
    assert snapshot.icon_custom_emoji_id == "987654321"
    assert snapshot.is_closed is True
    assert snapshot.is_pinned is True
    assert snapshot.creator_peer_id == 123


def test_telethon_proxy_uses_existing_http_gateway(monkeypatch):
    monkeypatch.setattr(
        telegram_userbot,
        "TELEGRAM_USERBOT_PROXY_URL",
        "http://proxy-user:proxy-pass@172.18.0.1:3129",
    )

    assert telegram_userbot._telethon_proxy() == (
        "http",
        "172.18.0.1",
        3129,
        True,
        "proxy-user",
        "proxy-pass",
    )


def test_telethon_app_message_header_is_not_mirrored_back_into_app_text():
    telegram_message = SimpleNamespace(message="Ada Lovelace · Elixir app\n\nUpdated text")
    current_message = SimpleNamespace(message="Татьяна · ↩️ Приложение\n\nПоняла, спасибо")
    logical = SimpleNamespace(source="app")

    assert telegram_userbot._telethon_message_text(telegram_message, logical) == "Updated text"
    assert telegram_userbot._archived_app_author_name(telegram_message) == "Ada Lovelace"
    assert telegram_userbot._telethon_message_text(current_message) == "Поняла, спасибо"
    assert telegram_userbot._archived_app_author_name(current_message) == "Татьяна"


def test_telethon_admin_log_message_classifies_edits_and_deletes():
    deleted = SimpleNamespace(
        deleted_message=True,
        changed_message=False,
        old=SimpleNamespace(id=41),
        new=None,
    )
    edited = SimpleNamespace(
        deleted_message=False,
        changed_message=True,
        old=SimpleNamespace(id=42),
        new=SimpleNamespace(id=42, message="updated"),
    )

    assert telegram_userbot._admin_log_message(deleted) == ("delete", deleted.old)
    assert telegram_userbot._admin_log_message(edited) == ("edit", edited.new)
