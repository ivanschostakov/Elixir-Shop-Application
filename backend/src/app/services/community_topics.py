from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import CommunityTopic


@dataclass(frozen=True, slots=True)
class TelegramForumTopicSnapshot:
    thread_id: int
    name: str
    icon_color: int | None = None
    icon_custom_emoji_id: str | None = None
    is_closed: bool = False
    is_hidden: bool = False
    is_pinned: bool = False
    top_message_id: int | None = None
    creator_peer_id: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TelegramTopicSyncResult:
    discovered: int
    updated: int
    restored: int
    deleted: int
    total: int


def apply_telegram_topic_snapshots(
    existing_topics: list[CommunityTopic],
    snapshots: list[TelegramForumTopicSnapshot],
    *,
    chat_id: int,
    synced_at: datetime | None = None,
) -> tuple[list[CommunityTopic], TelegramTopicSyncResult]:
    """Apply one complete, authoritative MTProto forum-topic snapshot."""
    if not snapshots:
        raise ValueError("Telegram returned an empty forum-topic snapshot")

    sync_time = synced_at or ufa_now()
    existing_by_thread = {
        int(topic.telegram_thread_id): topic
        for topic in existing_topics
        if int(topic.telegram_chat_id) == int(chat_id)
    }
    snapshots_by_thread = {int(snapshot.thread_id): snapshot for snapshot in snapshots}
    discovered = 0
    updated = 0
    restored = 0
    deleted = 0
    new_topics: list[CommunityTopic] = []

    for thread_id, snapshot in snapshots_by_thread.items():
        topic = existing_by_thread.get(thread_id)
        if topic is None:
            topic = CommunityTopic(
                telegram_chat_id=chat_id,
                telegram_thread_id=thread_id,
                name=(snapshot.name or f"Topic {thread_id}")[:128],
            )
            existing_by_thread[thread_id] = topic
            new_topics.append(topic)
            discovered += 1
        else:
            if topic.is_deleted:
                restored += 1
            before = (
                topic.name,
                topic.icon_color,
                topic.icon_custom_emoji_id,
                topic.is_closed,
                topic.is_hidden,
                topic.is_pinned,
                topic.telegram_top_message_id,
                topic.telegram_creator_peer_id,
                topic.telegram_created_at,
            )
            after = (
                (snapshot.name or topic.name or f"Topic {thread_id}")[:128],
                snapshot.icon_color,
                snapshot.icon_custom_emoji_id,
                snapshot.is_closed,
                snapshot.is_hidden,
                snapshot.is_pinned,
                snapshot.top_message_id,
                snapshot.creator_peer_id,
                snapshot.created_at,
            )
            if before != after:
                updated += 1

        topic.name = (snapshot.name or topic.name or f"Topic {thread_id}")[:128]
        topic.icon_color = snapshot.icon_color
        topic.icon_custom_emoji_id = snapshot.icon_custom_emoji_id
        topic.is_closed = snapshot.is_closed
        topic.is_hidden = snapshot.is_hidden
        topic.is_pinned = snapshot.is_pinned
        topic.is_deleted = False
        topic.telegram_top_message_id = snapshot.top_message_id
        topic.telegram_creator_peer_id = snapshot.creator_peer_id
        topic.telegram_created_at = snapshot.created_at
        topic.telegram_synced_at = sync_time

    active_thread_ids = set(snapshots_by_thread)
    for topic in existing_topics:
        if int(topic.telegram_chat_id) != int(chat_id):
            continue
        if int(topic.telegram_thread_id) in active_thread_ids:
            continue
        if not topic.is_deleted:
            deleted += 1
        topic.is_deleted = True
        topic.telegram_synced_at = sync_time

    result = TelegramTopicSyncResult(
        discovered=discovered,
        updated=updated,
        restored=restored,
        deleted=deleted,
        total=len(snapshots_by_thread),
    )
    return new_topics, result


async def reconcile_telegram_forum_topics(
    db: AsyncSession,
    *,
    chat_id: int,
    snapshots: list[TelegramForumTopicSnapshot],
) -> TelegramTopicSyncResult:
    existing_topics = list(
        (
            await db.execute(
                select(CommunityTopic).where(CommunityTopic.telegram_chat_id == chat_id)
            )
        )
        .scalars()
        .all()
    )
    new_topics, result = apply_telegram_topic_snapshots(
        existing_topics,
        snapshots,
        chat_id=chat_id,
    )
    db.add_all(new_topics)
    await db.commit()
    return result
