from datetime import datetime
from fastapi import HTTPException, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_COMMUNITY_JOIN_URL, ufa_now
from src.database.schemas.community import CommunityAttachmentRead, CommunityAuthorRead, CommunityMessagePageRead, CommunityMessageRead, CommunityReactionRead, CommunityReplyPreviewRead, CommunityTopicListRead, CommunityTopicRead
from src.database.models import CommunityMessage, CommunityReaction, CommunityTopic, CommunityTopicRead as CommunityTopicReadModel, User
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient, get_telegram_bot_client
from .common import COMMUNITY_REACTION_EMOJIS
from .reactions import _normalize_reaction_emoji
from .media import build_community_media_url
from .access import require_community_access
from .blocks import blocked_community_author_ids, visible_community_message
from .telegram_helpers import _delete_telegram_message_ids


def _message_options():
    return (selectinload(CommunityMessage.author), selectinload(CommunityMessage.attachments), selectinload(CommunityMessage.telegram_parts), selectinload(CommunityMessage.reply_to).selectinload(CommunityMessage.author), selectinload(CommunityMessage.reactions), selectinload(CommunityMessage.telegram_reactions), selectinload(CommunityMessage.telegram_reaction_counts),)


def _telegram_message_url(message: CommunityMessage) -> str | None:
    active_parts = [part for part in message.telegram_parts if part.deleted_at is None]
    if not active_parts: return TELEGRAM_COMMUNITY_JOIN_URL
    telegram_message_id = active_parts[0].telegram_message_id
    internal_chat_id = str(abs(TELEGRAM_COMMUNITY_CHAT_ID))
    if internal_chat_id.startswith("100"): internal_chat_id = internal_chat_id[3:]
    thread = message.topic.telegram_thread_id if message.topic else 0
    suffix = f"?thread={thread}" if thread else ""
    return f"https://t.me/c/{internal_chat_id}/{telegram_message_id}{suffix}"


def _serialize_reactions(message: CommunityMessage, *, user_id: int) -> list[CommunityReactionRead]:
    reaction_counts: dict[str, int] = {}
    my_reactions: set[str] = set()
    for reaction in message.reactions:
        emoji = _normalize_reaction_emoji(reaction.emoji)
        reaction_counts[emoji] = reaction_counts.get(emoji, 0) + 1
        if reaction.user_id == user_id: my_reactions.add(emoji)

    # Anonymous Telegram chats publish authoritative counts, while ordinary
    # chats publish one actor delta at a time. Never add both representations
    # for the same Telegram message part or those reactions would be doubled.
    telegram_count_rows = getattr(message, "telegram_reaction_counts", [])
    authoritative_parts = {(reaction.telegram_chat_id, reaction.telegram_message_id) for reaction in telegram_count_rows}
    for reaction in telegram_count_rows:
        if reaction.total_count <= 0: continue
        emoji = _normalize_reaction_emoji(reaction.emoji)
        reaction_counts[emoji] = reaction_counts.get(emoji, 0) + reaction.total_count
    for reaction in getattr(message, "telegram_reactions", []):
        part_key = (reaction.telegram_chat_id, reaction.telegram_message_id)
        if part_key in authoritative_parts: continue
        emoji = _normalize_reaction_emoji(reaction.emoji)
        reaction_counts[emoji] = reaction_counts.get(emoji, 0) + 1

    ordered_emojis = [emoji for emoji in COMMUNITY_REACTION_EMOJIS if reaction_counts.get(emoji)]
    ordered_emojis.extend(sorted(set(reaction_counts) - set(COMMUNITY_REACTION_EMOJIS)))
    return [CommunityReactionRead(emoji=emoji, count=reaction_counts[emoji], reacted_by_me=emoji in my_reactions) for emoji in ordered_emojis]


def serialize_community_message(message: CommunityMessage, *, request: Request, user_id: int, blocked_author_ids: set[int] | None = None) -> CommunityMessageRead:
    author = message.author
    author_read = CommunityAuthorRead(id=author.id if author else 0, full_name=author.full_name if author else "Telegram member", avatar_url=build_community_media_url(request, media_type="author", media_id=author.id, user_id=user_id) if author and author.avatar_local_filename else None, is_current_user=message.app_user_id == user_id)
    attachments = [] if message.deleted_at else [CommunityAttachmentRead(id=item.id, kind=item.kind, filename=item.original_filename or item.filename, mime_type=item.mime_type, size_bytes=item.size_bytes, media_url=build_community_media_url(request, media_type="attachment", media_id=item.id, user_id=user_id) if item.local_filename and item.status == "ready" else None, available_in_telegram=not bool(item.local_filename)) for item in message.attachments]
    reply = None
    if message.reply_to and not message.reply_to.deleted_at and message.reply_to.author_id not in (blocked_author_ids or set()): reply = CommunityReplyPreviewRead(id=message.reply_to.id, author_id=message.reply_to.author_id, author_name=message.reply_to.author.full_name if message.reply_to.author else "Telegram member", text=(message.reply_to.text or "Attachment")[:160])
    can_mutate = message.source == "app" and message.app_user_id == user_id and not message.deleted_at
    return CommunityMessageRead(id=message.id, topic_id=message.topic_id, author=author_read, text="" if message.deleted_at else message.text, attachments=attachments, reply_to=reply, reactions=_serialize_reactions(message, user_id=user_id), unsupported_type=None if message.deleted_at else message.unsupported_type, telegram_url=_telegram_message_url(message), delivery_status=message.delivery_status, is_edited=bool(message.edited_at), is_deleted=bool(message.deleted_at), can_edit=can_mutate, can_delete=can_mutate, edited_at=message.edited_at, created_at=message.sent_at)


async def _initialize_read_baseline(db: AsyncSession, *, user_id: int, topics: list[CommunityTopic]) -> None:
    existing_count = int((await db.execute(select(func.count(CommunityTopicReadModel.id)).where(CommunityTopicReadModel.user_id == user_id))).scalar_one())
    if existing_count or not topics: return
    for topic in topics: db.add(CommunityTopicReadModel(user_id=user_id, topic_id=topic.id, last_read_message_id=topic.last_message_id))
    await db.commit()


async def list_community_topics(db: AsyncSession, *, user: User, request: Request) -> CommunityTopicListRead:
    await require_community_access(user)
    topics = list((await db.execute(select(CommunityTopic).where(CommunityTopic.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTopic.is_hidden.is_(False), CommunityTopic.is_deleted.is_(False)).order_by(CommunityTopic.last_message_at.desc().nullslast(), CommunityTopic.name.asc()))).scalars().all())
    await _initialize_read_baseline(db, user_id=user.id, topics=topics)
    topic_ids = [topic.id for topic in topics]
    topic_by_id = {topic.id: topic for topic in topics}
    blocked_ids = await blocked_community_author_ids(db, user.id)
    last_visible_ids = select(func.max(CommunityMessage.id)).where(CommunityMessage.topic_id.in_(topic_ids), CommunityMessage.deleted_at.is_(None), visible_community_message(user.id)).group_by(CommunityMessage.topic_id)
    last_messages = list((await db.execute(select(CommunityMessage).where(CommunityMessage.id.in_(last_visible_ids)).options(*_message_options()))).scalars().all())
    last_message_by_topic = {message.topic_id: message for message in last_messages}
    for message in last_messages: message.topic = topic_by_id.get(message.topic_id)

    unread_rows = (await db.execute(select(CommunityMessage.topic_id, func.count(CommunityMessage.id)).outerjoin(CommunityTopicReadModel, and_(CommunityTopicReadModel.topic_id == CommunityMessage.topic_id, CommunityTopicReadModel.user_id == user.id,),).where(CommunityMessage.topic_id.in_(topic_ids) if topic_ids else False, CommunityMessage.id > func.coalesce(CommunityTopicReadModel.last_read_message_id, 0), CommunityMessage.deleted_at.is_(None), visible_community_message(user.id), or_(CommunityMessage.app_user_id.is_(None), CommunityMessage.app_user_id != user.id),).group_by(CommunityMessage.topic_id))).all()
    unread_by_topic = {int(topic_id): int(count) for topic_id, count in unread_rows}
    topic_reads: list[CommunityTopicRead] = []
    total_unread = 0
    for topic in topics:
        last_message = last_message_by_topic.get(topic.id)
        unread = unread_by_topic.get(topic.id, 0)
        total_unread += unread
        topic_reads.append(CommunityTopicRead(id=topic.id, name=topic.name, icon_color=topic.icon_color, icon_custom_emoji_id=topic.icon_custom_emoji_id, is_closed=topic.is_closed, last_message=serialize_community_message(last_message, request=request, user_id=user.id, blocked_author_ids=blocked_ids) if last_message else None, unread_count=unread))
    return CommunityTopicListRead(topics=topic_reads, total_unread=total_unread, blocked_author_ids=sorted(blocked_ids))


async def list_community_messages(db: AsyncSession, *, user: User, request: Request, topic_id: int, before_id: int | None, after_id: int | None, changed_after: datetime | None, changed_after_id: int, limit: int) -> CommunityMessagePageRead:
    await require_community_access(user)
    blocked_ids = await blocked_community_author_ids(db, user.id)
    sync_cursor = ufa_now()
    sync_cursor_id = 0
    if before_id and after_id: raise HTTPException(status_code=422, detail="before_id and after_id cannot be combined")
    topic = await db.get(CommunityTopic, topic_id)
    if topic is None or topic.telegram_chat_id != TELEGRAM_COMMUNITY_CHAT_ID or topic.is_deleted: raise HTTPException(status_code=404, detail="Community topic not found")
    stmt = select(CommunityMessage).where(CommunityMessage.topic_id == topic_id, visible_community_message(user.id)).options(*_message_options())
    if after_id:
        new_rows = list((await db.execute(stmt.where(CommunityMessage.id > after_id).order_by(CommunityMessage.id.asc()).limit(limit + 1))).scalars().all())
        has_more = len(new_rows) > limit
        new_rows = new_rows[:limit]
        if changed_after:
            changed_rows = list((await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic_id, visible_community_message(user.id), CommunityMessage.id <= after_id, or_(CommunityMessage.updated_at > changed_after, and_(CommunityMessage.updated_at == changed_after, CommunityMessage.id > changed_after_id,),), CommunityMessage.updated_at <= sync_cursor,).order_by(CommunityMessage.updated_at.asc(), CommunityMessage.id.asc()).limit(limit + 1).options(*_message_options()))).scalars().all())
            changed_has_more = len(changed_rows) > limit
            has_more = has_more or changed_has_more
            changed_rows = changed_rows[:limit]
            if changed_has_more and changed_rows:
                sync_cursor = changed_rows[-1].updated_at
                sync_cursor_id = changed_rows[-1].id
        else:
            # Backward-compatible reconciliation for clients without a change cursor.
            changed_rows = list((await db.execute(select(CommunityMessage).where(CommunityMessage.topic_id == topic_id, CommunityMessage.id <= after_id, visible_community_message(user.id)).order_by(CommunityMessage.id.desc()).limit(20).options(*_message_options()))).scalars().all())
        rows = sorted({row.id: row for row in [*changed_rows, *new_rows]}.values(), key=lambda row: row.id)
    else:
        if before_id: stmt = stmt.where(CommunityMessage.id < before_id)
        stmt = stmt.order_by(CommunityMessage.id.desc())
        rows = list((await db.execute(stmt.limit(limit + 1))).scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        rows.reverse()
    for row in rows: row.topic = topic
    return CommunityMessagePageRead(blocked_author_ids=sorted(blocked_ids), messages=[serialize_community_message(row, request=request, user_id=user.id, blocked_author_ids=blocked_ids) for row in rows], has_more=has_more, oldest_id=rows[0].id if rows else None, newest_id=rows[-1].id if rows else None, sync_cursor=sync_cursor, sync_cursor_id=sync_cursor_id)


async def mark_community_topic_read(db: AsyncSession, *, user: User, topic_id: int, last_message_id: int) -> None:
    await require_community_access(user)
    message = await db.get(CommunityMessage, last_message_id)
    if message is None or message.topic_id != topic_id: raise HTTPException(status_code=404, detail="Community message not found")
    read_state = (await db.execute(select(CommunityTopicReadModel).where(CommunityTopicReadModel.user_id == user.id, CommunityTopicReadModel.topic_id == topic_id))).scalar_one_or_none()
    if read_state is None: db.add(CommunityTopicReadModel(user_id=user.id, topic_id=topic_id, last_read_message_id=last_message_id))
    elif not read_state.last_read_message_id or last_message_id > read_state.last_read_message_id: read_state.last_read_message_id = last_message_id
    await db.commit()


async def toggle_community_message_reaction(db: AsyncSession, *, user: User, topic_id: int, message_id: int, emoji: str, telegram_client: TelegramBotClient | None = None,) -> list[CommunityReactionRead]:
    await require_community_access(user)
    normalized_emoji = _normalize_reaction_emoji(emoji)
    if normalized_emoji not in COMMUNITY_REACTION_EMOJIS: raise HTTPException(status_code=422, detail="Unsupported reaction")
    message = (await db.execute(select(CommunityMessage).where(CommunityMessage.id == message_id, CommunityMessage.topic_id == topic_id, CommunityMessage.deleted_at.is_(None), visible_community_message(user.id)).options(selectinload(CommunityMessage.reactions), selectinload(CommunityMessage.telegram_parts), selectinload(CommunityMessage.topic),).with_for_update())).scalar_one_or_none()
    if message is None: raise HTTPException(status_code=404, detail="Community message not found")
    existing = next((reaction for reaction in message.reactions if reaction.user_id == user.id and reaction.emoji == normalized_emoji), None)
    if existing:
        if existing.telegram_message_id:
            try:
                client = telegram_client or get_telegram_bot_client()
                await _delete_telegram_message_ids(
                    client,
                    chat_id=existing.telegram_chat_id or TELEGRAM_COMMUNITY_CHAT_ID,
                    message_ids=[existing.telegram_message_id],
                )
            except (TelegramBotAPIError, TimeoutError, OSError) as exc: raise HTTPException(status_code=502, detail="Telegram could not remove the reaction reply",) from exc
        await db.delete(existing)
        reaction = None
    else:
        reaction = CommunityReaction(message_id=message.id, user_id=user.id, emoji=normalized_emoji, delivery_status="queued",)
        db.add(reaction)
    # Message polling uses the parent timestamp as its reconciliation cursor.
    message.updated_at = ufa_now()
    await db.commit()
    message = (await db.execute(select(CommunityMessage).where(CommunityMessage.id == message_id).options(selectinload(CommunityMessage.reactions), selectinload(CommunityMessage.telegram_reactions), selectinload(CommunityMessage.telegram_reaction_counts),))).scalar_one()
    return _serialize_reactions(message, user_id=user.id)
