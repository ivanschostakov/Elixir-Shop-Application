"""Destructive-account and visibility regressions, isolated PostgreSQL only."""
import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from test_ai_companion_db import database, URL
from config import ufa_now
from src.database import models as m
from src.app.services.auth.account_erasure import erase_account
from src.app.services import community
from src.integrations.ai.enums import MessageSender, AttachmentType

pytestmark = pytest.mark.skipif(not URL, reason="Set an isolated COMPANION_TEST_DB_URL")


def address(user_id, label="Saved address"):
    return m.DeliveryAddress(user_id=user_id, mode="door", provider="CDEK", country_code="RU", name=label, full_address=label, latitude=1, longitude=1)


def test_account_erasure_removes_identity_personal_rows_files_and_queues_provider(monkeypatch, tmp_path):
    import config
    import src.database.models.ai.attachment as attachment_model
    monkeypatch.setattr(config, "ATTACHMENTS_DIR", tmp_path / "public")
    monkeypatch.setattr(attachment_model, "ATTACHMENTS_DIR", tmp_path / "public")
    async def run():
        async with database() as (db, user):
            user.email = f"erase-{uuid4().hex}@example.test"
            user.username = f"erase-{uuid4().hex}"
            user.telegram_user_id = 919292939
            user.telegram_username = "erase_me"
            user_id, email = user.id, user.email
            other = m.User(name="Keep", surname="Other", password_hash="test")
            db.add(other)
            await db.flush()
            db.add_all([address(user_id), address(other.id, "Other saved address"), m.UserSession(user_id=user_id, refresh_token_hash="test"), m.UserDevice(user_id=user_id, installation_id="test-installation", platform="ios"), m.AICompanionProfile(user_id=user_id, data={"private": "health"}), m.TelegramAIProfile(telegram_user_id=user.telegram_user_id, data={"private": "health"})])
            chat = m.AIChat(user_id=user_id, conversation_id="conv_erasure_test")
            db.add(chat)
            await db.flush()
            message = m.AIMessage(user_id=user_id, chat_id=chat.id, text="Private ordinary message", sender=MessageSender.USER)
            db.add(message)
            await db.flush()
            attachment = m.Attachment(message_id=message.id, filename="erase.txt", type=AttachmentType.DOCUMENT, size_bytes=7)
            db.add(attachment)
            await db.flush()
            file_path = attachment.path
            file_path.parent.mkdir(parents=True)
            file_path.write_text("private")
            await erase_account(db, user)
            assert (await db.execute(select(m.User.id).where(m.User.id == user_id))).scalar_one_or_none() is None
            for model in (m.AIChat, m.AIMessage, m.DeliveryAddress, m.UserSession, m.UserDevice, m.AICompanionProfile):
                assert not (await db.execute(select(model).where(model.user_id == user_id))).scalars().all(), model
            assert not file_path.exists()
            assert (await db.execute(select(m.User.id).where(m.User.id == other.id))).scalar_one() == other.id
            assert (await db.execute(select(m.DeliveryAddress).where(m.DeliveryAddress.user_id == other.id))).scalar_one().full_address == "Other saved address"
            assert not (await db.execute(select(m.TelegramAIProfile).where(m.TelegramAIProfile.telegram_user_id == 919292939))).scalars().all()
            resource = (await db.execute(select(m.AIProviderResource).where(m.AIProviderResource.external_id == "conv_erasure_test"))).scalar_one()
            assert resource.user_id is None and resource.status == "pending_delete"
            # Identity can be registered again, but the old account ID stays gone.
            db.add(m.User(name="New", surname="Account", email=email, password_hash="new"))
            await db.flush()
    asyncio.run(run())


def test_erasure_retains_submitted_order_but_not_saved_addresses_or_drafts():
    async def run():
        async with database() as (db, user):
            user_id = user.id
            used, unused = address(user_id, "Order address"), address(user_id, "Unused address")
            recipient = m.DeliveryRecipient(user_id=user_id, name="Buyer", surname="Name", phone="+79991234567")
            db.add_all([used, unused, recipient])
            await db.flush()
            draft = m.OrderDraft(user_id=user_id, delivery_address_id=used.id, recipient_id=recipient.id)
            db.add(draft)
            await db.flush()
            order = m.Order(user_id=user_id, draft_id=draft.id, delivery_address_id=used.id, recipient_id=recipient.id, order_code=f"ERASE-{uuid4().hex[:16]}")
            db.add(order)
            await db.flush()
            order_id, used_id, unused_id = order.id, used.id, unused.id
            await erase_account(db, user)
            db.expire_all()
            kept = (await db.execute(select(m.Order).where(m.Order.id == order_id))).scalar_one()
            assert kept.user_id != user_id and kept.draft_id is None
            owner = (await db.execute(select(m.User).where(m.User.id == kept.user_id))).scalar_one()
            assert not owner.is_active and not owner.is_verified
            assert owner.email is None and owner.telegram_user_id is None and owner.username is None and owner.phone_number is None
            assert (await db.execute(select(m.User.id).where(m.User.id == user_id))).scalar_one_or_none() is None
            assert (await db.execute(select(m.DeliveryAddress.user_id).where(m.DeliveryAddress.id == used_id))).scalar_one() == kept.user_id
            assert (await db.execute(select(m.DeliveryAddress.id).where(m.DeliveryAddress.id == unused_id))).scalar_one_or_none() is None
            assert not (await db.execute(select(m.OrderDraft).where(m.OrderDraft.user_id == user_id))).scalars().all()
    asyncio.run(run())


def test_blocks_hide_history_replies_previews_unread_and_linked_aliases(monkeypatch):
    async def allowed(*args, **kwargs): pass
    monkeypatch.setattr(community, "require_community_access", allowed)
    monkeypatch.setattr(community, "TELEGRAM_COMMUNITY_CHAT_ID", -100123)
    request = Request({"type": "http", "method": "GET", "scheme": "https", "path": "/", "headers": [], "server": ("example.test", 443)})
    async def run():
        async with database() as (db, viewer):
            writer = m.User(name="Writer", surname="Member", password_hash="test")
            db.add(writer)
            await db.flush()
            topic = m.CommunityTopic(telegram_chat_id=-100123, telegram_thread_id=1, name="Topic")
            author = m.CommunityAuthor(kind="app", telegram_peer_id=writer.id, app_user_id=writer.id, full_name="Writer")
            alias = m.CommunityAuthor(kind="user", telegram_peer_id=123456, app_user_id=writer.id, full_name="Writer Telegram")
            own = m.CommunityAuthor(kind="app", telegram_peer_id=viewer.id, app_user_id=viewer.id, full_name="Viewer")
            db.add_all([topic, author, alias, own])
            await db.flush()
            first = m.CommunityMessage(topic_id=topic.id, author_id=own.id, app_user_id=viewer.id, source="app", text="Visible", sent_at=ufa_now())
            blocked = m.CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=writer.id, source="app", text="Hidden", sent_at=ufa_now())
            db.add_all([first, blocked]); await db.flush()
            reply = m.CommunityMessage(topic_id=topic.id, author_id=own.id, app_user_id=viewer.id, reply_to_message_id=blocked.id, source="app", text="Visible reply", sent_at=ufa_now())
            hidden_alias = m.CommunityMessage(topic_id=topic.id, author_id=alias.id, app_user_id=writer.id, source="telegram", text="Hidden alias", sent_at=ufa_now())
            db.add_all([reply, hidden_alias]); await db.flush()
            topic.last_message_id = hidden_alias.id
            topic.last_message_at = hidden_alias.sent_at
            db.add(m.CommunityTopicRead(user_id=viewer.id, topic_id=topic.id, last_read_message_id=first.id))
            await db.flush()
            await community.block_community_author(db, user=viewer, author_id=author.id)
            await community.block_community_author(db, user=viewer, author_id=author.id)
            with pytest.raises(HTTPException) as error:
                await community.block_community_author(db, user=viewer, author_id=own.id)
            assert error.value.status_code == 422
            kwargs = dict(request=request, topic_id=topic.id, before_id=None, after_id=None, changed_after=None, changed_after_id=0, limit=1)
            page = await community.list_community_messages(db, user=viewer, **kwargs)
            assert [msg.id for msg in page.messages] == [reply.id]
            assert page.has_more and page.messages[0].reply_to is None
            assert set(page.blocked_author_ids) == {author.id, alias.id}
            older = await community.list_community_messages(db, user=viewer, **{**kwargs, "before_id": reply.id})
            assert [msg.id for msg in older.messages] == [first.id]
            topics = await community.list_community_topics(db, user=viewer, request=request)
            assert topics.total_unread == 0 and topics.topics[0].last_message.id == reply.id
            delta = await community.list_community_messages(db, user=viewer, **{**kwargs, "limit": 100, "after_id": first.id, "changed_after": ufa_now() - timedelta(days=1)})
            assert {msg.id for msg in delta.messages} <= {first.id, reply.id}
            other_view = await community.list_community_messages(db, user=writer, **{**kwargs, "limit": 100})
            assert len(other_view.messages) == 4
            await community.unblock_community_author(db, user=viewer, author_id=author.id)
            restored = await community.list_community_messages(db, user=viewer, **{**kwargs, "limit": 100})
            assert len(restored.messages) == 4 and restored.messages[2].reply_to.text == "Hidden"
    asyncio.run(run())


def test_local_erasure_cannot_escape_storage_root(tmp_path, monkeypatch):
    import config
    from src.app.services.ai.companion.jobs import delete_provider_resource
    monkeypatch.setattr(config, "ATTACHMENTS_DIR", tmp_path / "attachments")
    target = tmp_path / "outside.txt"
    target.write_text("Keep")
    with pytest.raises(ValueError):
        asyncio.run(delete_provider_resource(None, "public_ai_file", "../outside.txt"))
    assert target.read_text() == "Keep"


def test_account_erasure_during_ordinary_ai_request_queues_late_provider_file(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.services.ai import chat as chat_service
    monkeypatch.setattr(chat_service, "record_customer_event_safe", AsyncMock())
    async def run():
        async with database() as (db, user):
            from src.app.services.ai.data_consent import set_ai_data_consent, AIDataConsentPayload, AI_DATA_CONSENT_VERSION
            await set_ai_data_consent(db, user.id, AIDataConsentPayload(granted=True, version=AI_DATA_CONSENT_VERSION))
            user_id = user.id
            async def respond(**kwargs):
                await erase_account(db, user)
                await kwargs["resource_recorder"]("file", "file_created_during_erasure")
                pytest.fail("A response must not continue after account erasure")
            professor = SimpleNamespace(create_conversation=AsyncMock(return_value="conv_inflight_account"), send_message_v2=respond, _resolve_model_name=lambda _: "mock")
            with pytest.raises(HTTPException) as error:
                await chat_service.send_user_chat_message(db, user=user, text="Hello", attachments=None, professor_client=professor, allow_commerce=False)
            assert error.value.status_code == 401
            assert not (await db.execute(select(m.AIMessage).where(m.AIMessage.user_id == user_id))).scalars().all()
            resource = (await db.execute(select(m.AIProviderResource).where(m.AIProviderResource.external_id == "file_created_during_erasure"))).scalar_one()
            assert resource.user_id is None and resource.status == "pending_delete"
    asyncio.run(run())


def test_deleted_community_content_cannot_return_from_telegram_edit(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "COMMUNITY_MEDIA_DIR", tmp_path)
    monkeypatch.setattr(community, "TELEGRAM_COMMUNITY_ENABLED", True)
    monkeypatch.setattr(community, "TELEGRAM_COMMUNITY_CHAT_ID", -100123)
    async def run():
        async with database() as (db, user):
            topic = m.CommunityTopic(telegram_chat_id=-100123, telegram_thread_id=1, name="Topic")
            author = m.CommunityAuthor(kind="app", telegram_peer_id=user.id, app_user_id=user.id, full_name="Private Name")
            db.add_all([topic, author]); await db.flush()
            message = m.CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=user.id, source="app", text="Private post", sent_at=ufa_now())
            db.add(message); await db.flush()
            db.add(m.CommunityTelegramPart(message_id=message.id, telegram_chat_id=-100123, telegram_message_id=777))
            db.add(m.CommunityAttachment(message_id=message.id, kind="document", filename="private.txt", local_filename="private.txt", size_bytes=7))
            await db.flush()
            path = tmp_path / "attachments" / "private.txt"
            path.parent.mkdir(); path.write_text("private")
            message_id, author_id = message.id, author.id
            await erase_account(db, user)
            db.expire_all()
            result = await community.process_community_telegram_message(db, {"edited_message": {"chat": {"id": -100123}, "message_id": 777, "text": "Private post restored"}})
            assert result["ignored"] == "deleted community message"
            post = (await db.execute(select(m.CommunityMessage).where(m.CommunityMessage.id == message_id))).scalar_one()
            assert post.text == "" and post.deleted_at is not None and post.app_user_id is None
            erased_author = (await db.execute(select(m.CommunityAuthor).where(m.CommunityAuthor.id == author_id))).scalar_one()
            assert erased_author.full_name == "Deleted member" and erased_author.app_user_id is None
            assert not path.exists()
    asyncio.run(run())
