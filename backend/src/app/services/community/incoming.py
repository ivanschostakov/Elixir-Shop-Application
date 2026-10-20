import time
from datetime import datetime
from typing import Any
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_COMMUNITY_ENABLED, TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES, ufa_now
from src.database.crud.auth.user import get_user_by_telegram_user_id
from src.database.models import CommunityAttachment, CommunityMessage, CommunityNotificationEvent, CommunityTelegramPart, CommunityTelegramReaction, CommunityTelegramReactionCount, CommunityTopic
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_ATTACHMENTS_DIR
from .reactions import _normalize_reaction_emoji, _telegram_reaction_actor_key, _telegram_reaction_emoji
from .media import _safe_filename
from .authors import _upsert_author
from .telegram_helpers import _is_telegram_app_reaction_notification


def _message_full_name(sender: dict[str, Any]) -> str:
    return " ".join(str(sender.get(key) or "").strip() for key in ("first_name", "last_name")).strip() or "Telegram member"


async def _get_or_create_topic(db: AsyncSession, *, thread_id: int, name: str | None = None) -> CommunityTopic:
    topic = (await db.execute(select(CommunityTopic).where(CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.telegram_thread_id == thread_id))).scalar_one_or_none()
    if topic is None:
        topic = CommunityTopic(telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_thread_id=thread_id, name=(name or ("General" if thread_id == 0 else f"Topic {thread_id}"))[:128])
        db.add(topic); await db.flush()
    elif name: topic.name = name[:128]
    topic.is_deleted = False
    return topic


async def _is_group_admin(telegram_client: TelegramBotClient, user_id: int) -> bool:
    try: return str((await telegram_client.get_chat_member(TELEGRAM_COMMUNITY_CHAT_ID, user_id)).get("status") or "") in {"creator", "administrator"}
    except (TelegramBotAPIError, TimeoutError): return False


async def process_community_telegram_reaction(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    detailed_update = payload.get("message_reaction")
    count_update = payload.get("message_reaction_count")
    update_payload = detailed_update if isinstance(detailed_update, dict) else count_update
    if not isinstance(update_payload, dict): return {"ok": True, "ignored": "no community reaction"}
    chat = update_payload.get("chat") if isinstance(update_payload.get("chat"), dict) else {}
    telegram_chat_id = int(chat.get("id") or 0)
    telegram_message_id = int(update_payload.get("message_id") or 0)
    if (not TELEGRAM_COMMUNITY_ENABLED or telegram_chat_id != TELEGRAM_COMMUNITY_CHAT_ID or telegram_message_id <= 0): return {"ok": True, "ignored": "wrong community reaction"}

    part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == telegram_chat_id, CommunityTelegramPart.telegram_message_id == telegram_message_id, CommunityTelegramPart.deleted_at.is_(None),))).scalar_one_or_none()
    if part is None: return {"ok": True, "ignored": "untracked community message"}
    message = await db.get(CommunityMessage, part.message_id)
    if message is None or message.deleted_at is not None: return {"ok": True, "ignored": "deleted community message"}

    changed = False
    if isinstance(detailed_update, dict):
        actor_key = _telegram_reaction_actor_key(detailed_update)
        if actor_key is None: return {"ok": True, "ignored": "reaction actor missing"}
        new_reaction_types = detailed_update.get("new_reaction")
        if not isinstance(new_reaction_types, list): new_reaction_types = []
        new_emojis = {emoji for emoji in (_telegram_reaction_emoji(reaction_type) for reaction_type in new_reaction_types) if emoji}
        existing_actor_rows = list((await db.execute(select(CommunityTelegramReaction).where(CommunityTelegramReaction.telegram_chat_id == telegram_chat_id, CommunityTelegramReaction.telegram_message_id == telegram_message_id, CommunityTelegramReaction.actor_key == actor_key,))).scalars().all())
        existing_emojis = {_normalize_reaction_emoji(row.emoji) for row in existing_actor_rows}
        for row in existing_actor_rows:
            if _normalize_reaction_emoji(row.emoji) not in new_emojis:
                await db.delete(row)
                changed = True
        for emoji in new_emojis - existing_emojis:
            db.add(CommunityTelegramReaction(message_id=message.id, telegram_chat_id=telegram_chat_id, telegram_message_id=telegram_message_id, actor_key=actor_key, emoji=emoji,))
            changed = True

        # A detailed actor update means this part is not using Telegram's
        # anonymous aggregate representation. Remove a stale snapshot if the
        # group's anonymity setting changed.
        stale_counts = list((await db.execute(select(CommunityTelegramReactionCount).where(CommunityTelegramReactionCount.telegram_chat_id == telegram_chat_id, CommunityTelegramReactionCount.telegram_message_id == telegram_message_id,))).scalars().all())
        for row in stale_counts:
            await db.delete(row)
            changed = True

    elif isinstance(count_update, dict):
        reaction_counts = count_update.get("reactions")
        incoming_counts: dict[str, int] = {}
        if isinstance(reaction_counts, list):
            for reaction_count in reaction_counts:
                if not isinstance(reaction_count, dict): continue
                emoji = _telegram_reaction_emoji(reaction_count.get("type"))
                total_count = max(int(reaction_count.get("total_count") or 0), 0)
                if emoji and total_count: incoming_counts[emoji] = total_count
        existing_count_rows = list((await db.execute(select(CommunityTelegramReactionCount).where(CommunityTelegramReactionCount.telegram_chat_id == telegram_chat_id, CommunityTelegramReactionCount.telegram_message_id == telegram_message_id,))).scalars().all())
        existing_count_by_emoji = {_normalize_reaction_emoji(row.emoji): row for row in existing_count_rows}
        for emoji, row in existing_count_by_emoji.items():
            if emoji not in incoming_counts:
                await db.delete(row)
                changed = True
            elif row.total_count != incoming_counts[emoji]:
                row.total_count = incoming_counts[emoji]
                changed = True
        for emoji, total_count in incoming_counts.items():
            if emoji not in existing_count_by_emoji:
                db.add(CommunityTelegramReactionCount(message_id=message.id, telegram_chat_id=telegram_chat_id, telegram_message_id=telegram_message_id, emoji=emoji, total_count=total_count,))
                changed = True

        # Anonymous count updates are authoritative for this Telegram part.
        # Remove prior per-actor state if the group's anonymity setting changed.
        stale_actor_rows = list((await db.execute(select(CommunityTelegramReaction).where(CommunityTelegramReaction.telegram_chat_id == telegram_chat_id, CommunityTelegramReaction.telegram_message_id == telegram_message_id,))).scalars().all())
        for row in stale_actor_rows:
            await db.delete(row)
            changed = True

    if changed:
        # The open-chat poll reconciles rows using the logical message cursor,
        # so advancing the parent makes the reaction appear immediately.
        message.updated_at = ufa_now()
    return {
        "ok": True,
        "community_message_id": message.id,
        "reaction_updated": changed,
    }


async def process_community_telegram_message(db: AsyncSession, payload: dict[str, Any], *, telegram_client: TelegramBotClient | None = None) -> dict[str, Any]:
    is_edit = isinstance(payload.get("edited_message"), dict)
    message = payload.get("edited_message") if is_edit else payload.get("message")
    if not isinstance(message, dict): return {"ok": True, "ignored": "no community message"}
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    if not TELEGRAM_COMMUNITY_ENABLED or int(chat.get("id") or 0) != TELEGRAM_COMMUNITY_CHAT_ID: return {"ok": True, "ignored": "wrong community chat"}
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    raw_text = str(message.get("text") or message.get("caption") or "")
    if bool(sender.get("is_bot")) and _is_telegram_app_reaction_notification(raw_text): return {"ok": True, "ignored": "app reaction notification"}
    telegram_message_id = int(message.get("message_id") or 0)
    existing_part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == telegram_message_id,).options(selectinload(CommunityTelegramPart.message)))).scalar_one_or_none()
    if existing_part:
        if not is_edit: return {"ok": True, "ignored": "duplicate"}
        logical = existing_part.message
        if logical.deleted_at is not None: return {"ok": True, "ignored": "deleted community message"}
        raw_text = str(message.get("text") or message.get("caption") or "")
        if logical.source == "app" and "\n\n" in raw_text: raw_text = raw_text.split("\n\n", 1)[1]
        logical.text = raw_text
        logical.edited_at = datetime.fromtimestamp(int(message.get("edit_date") or time.time()), tz=ufa_now().tzinfo,)
        logical.deleted_at = None
        existing_part.deleted_at = None
        return {"ok": True, "community_message_id": logical.id, "edited": True}
    client = telegram_client or get_telegram_bot_client()
    thread_id = int(message.get("message_thread_id") or 0)
    if raw_text.startswith("/register"):
        sender_id = int(sender.get("id") or 0)
        if not sender_id or not await _is_group_admin(client, sender_id): return {"ok": True, "ignored": "register requires admin"}
        name = raw_text.partition(" ")[2].strip() or ("General" if thread_id == 0 else f"Topic {thread_id}")
        await _get_or_create_topic(db, thread_id=thread_id, name=name); await db.commit()
        try: await client.delete_message(TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id)
        except (TelegramBotAPIError, TimeoutError): pass
        return {"ok": True, "registered_thread_id": thread_id}
    created = message.get("forum_topic_created") if isinstance(message.get("forum_topic_created"), dict) else None
    edited = message.get("forum_topic_edited") if isinstance(message.get("forum_topic_edited"), dict) else None
    topic = await _get_or_create_topic(db, thread_id=thread_id, name=str((created or edited or {}).get("name") or "") or None)
    if created:
        topic.icon_color = created.get("icon_color"); topic.icon_custom_emoji_id = created.get("icon_custom_emoji_id")
    if edited and "icon_custom_emoji_id" in edited: topic.icon_custom_emoji_id = edited.get("icon_custom_emoji_id") or None
    if message.get("forum_topic_closed") is not None: topic.is_closed = True
    if message.get("forum_topic_reopened") is not None: topic.is_closed = False
    if message.get("general_forum_topic_hidden") is not None: topic.is_hidden = True
    if message.get("general_forum_topic_unhidden") is not None: topic.is_hidden = False
    if created or edited or message.get("forum_topic_closed") is not None or message.get("forum_topic_reopened") is not None or message.get("general_forum_topic_hidden") is not None or message.get("general_forum_topic_unhidden") is not None:
        await db.commit(); return {"ok": True, "topic_updated": topic.id}
    sender_chat = message.get("sender_chat") if isinstance(message.get("sender_chat"), dict) else None
    if sender_chat:
        peer_id = int(sender_chat.get("id") or 0); kind = "chat"; full_name = str(sender_chat.get("title") or "Telegram")
    else:
        peer_id = int(sender.get("id") or 0); kind = "user"; full_name = _message_full_name(sender)
    linked_user = await get_user_by_telegram_user_id(db, peer_id) if kind == "user" and peer_id else None
    author = await _upsert_author(db, kind=kind, telegram_peer_id=peer_id or -telegram_message_id, full_name=full_name, app_user_id=linked_user.id if linked_user else None, telegram_client=client, refresh_avatar=False)
    media_group_id = str(message.get("media_group_id") or "") or None
    logical = None
    created_logical = False
    if media_group_id: logical = (await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic.id, CommunityMessage.telegram_media_group_id == media_group_id).order_by(CommunityMessage.id.asc()).limit(1))).scalar_one_or_none()
    if logical is None:
        reply_to = None
        reply_payload = message.get("reply_to_message") if isinstance(message.get("reply_to_message"), dict) else None
        if reply_payload:
            reply_part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == int(reply_payload.get("message_id") or 0)))).scalar_one_or_none()
            reply_to = reply_part.message_id if reply_part else None
        sent_at = datetime.fromtimestamp(int(message.get("date") or time.time()), tz=ufa_now().tzinfo)
        logical = CommunityMessage(topic_id=topic.id, author_id=author.id, app_user_id=linked_user.id if linked_user else None, reply_to_message_id=reply_to, source="telegram", telegram_media_group_id=media_group_id, text=raw_text, delivery_status="sent", sent_at=sent_at)
        db.add(logical); await db.flush()
        db.add(CommunityNotificationEvent(message_id=logical.id))
        created_logical = True
    elif logical.deleted_at is not None: return {"ok": True, "ignored": "deleted community message"}
    elif raw_text and not logical.text: logical.text = raw_text
    photo_sizes = message.get("photo") if isinstance(message.get("photo"), list) else []
    document = message.get("document") if isinstance(message.get("document"), dict) else None
    voice = message.get("voice") if isinstance(message.get("voice"), dict) else None
    audio = message.get("audio") if isinstance(message.get("audio"), dict) else None
    audio_payload = voice or audio
    if audio_payload: logical.unsupported_type = None
    file_payload = max([item for item in photo_sizes if isinstance(item, dict)], key=lambda item: int(item.get("file_size") or 0), default=None) if photo_sizes else document or audio_payload
    attachment: CommunityAttachment | None = None
    file_id = ""
    if file_payload:
        file_id = str(file_payload.get("file_id") or "")
        fallback_name = f"photo-{telegram_message_id}.jpg" if photo_sizes else f"voice-{telegram_message_id}.ogg" if voice else f"audio-{telegram_message_id}" if audio else f"file-{telegram_message_id}"
        original = _safe_filename(file_payload.get("file_name"), fallback_name)
        fallback_mime_type = "image/jpeg" if photo_sizes else "audio/ogg" if voice else "audio/mpeg" if audio else "application/octet-stream"
        mime_type = str(file_payload.get("mime_type") or fallback_mime_type)
        attachment = CommunityAttachment(message_id=logical.id, kind="image" if photo_sizes else "document", original_filename=original, filename=f"telegram-{telegram_message_id}", mime_type=mime_type, size_bytes=int(file_payload.get("file_size") or 0), telegram_file_id=file_id, telegram_file_unique_id=str(file_payload.get("file_unique_id") or "") or None, telegram_message_id=telegram_message_id, status="telegram_only")
        db.add(attachment); await db.flush()
        # Media-group parts can arrive after the logical bubble was already
        # shown. Advance its cursor even when Telegram keeps the file remote.
        logical.updated_at = ufa_now()
    unsupported_keys = ("video", "video_note", "sticker", "animation", "poll", "location", "contact")
    for key in unsupported_keys:
        if message.get(key) is not None: logical.unsupported_type = key; break
    db.add(CommunityTelegramPart(message_id=logical.id, telegram_chat_id=TELEGRAM_COMMUNITY_CHAT_ID, telegram_message_id=telegram_message_id))
    if not topic.last_message_at or logical.sent_at >= topic.last_message_at:
        topic.last_message_id = logical.id; topic.last_message_at = logical.sent_at
    # Make the mirrored message visible before slower Telegram media/profile downloads.
    await db.commit()
    await _upsert_author(db, kind=kind, telegram_peer_id=peer_id or -telegram_message_id, full_name=full_name, app_user_id=linked_user.id if linked_user else None, telegram_client=client)
    # The avatar refresh mutates the author row, which is outside the message
    # cursor. Re-emit this bubble so clients replace its avatar URL promptly.
    logical.updated_at = ufa_now()
    await db.commit()
    if attachment and file_id and attachment.size_bytes <= TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES:
        local_filename = f"{logical.id}-{uuid4().hex}"
        try:
            attachment.size_bytes = await client.download_file(file_id, COMMUNITY_ATTACHMENTS_DIR / local_filename, max_bytes=TELEGRAM_COMMUNITY_MAX_DOWNLOAD_BYTES)
            attachment.local_filename = local_filename; attachment.status = "ready"
            logical.updated_at = ufa_now()
            await db.commit()
        except (TelegramBotAPIError, TimeoutError, OSError):
            pass
    return {"ok": True, "community_message_id": logical.id, "created": created_logical}
