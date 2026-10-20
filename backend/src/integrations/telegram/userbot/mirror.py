import asyncio
from contextlib import suppress
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config import TELEGRAM_COMMUNITY_CHAT_ID, TELEGRAM_USERBOT_HISTORY_SYNC_INTERVAL_SECONDS, TELEGRAM_USERBOT_TOPIC_SYNC_INTERVAL_SECONDS
from src.app.services.community import mark_community_telegram_messages_deleted
from src.database import get_session
from src.database.models import CommunityMessage, CommunityTelegramPart
from .common import log
from .session import _build_client, _lock_down_session_file, _require_authorized_user, _resolve_forum_peer
from .topics import _sync_telegram_forum_topics_with_client
from .messages import _upsert_telethon_message
from .history import _sync_telegram_forum_history_with_client
from .admin_log import _run_telegram_admin_log_reconciler


async def run_telegram_userbot_mirror(stop_event: asyncio.Event) -> None:
    """Continuously reconcile topics/history and receive Telegram edit/delete events."""
    from telethon import events

    retry_seconds = 10
    while not stop_event.is_set():
        client = _build_client(receive_updates=True)
        admin_log_task: asyncio.Task[None] | None = None
        try:
            await client.connect()
            await _require_authorized_user(client)

            async def handle_edit(event: Any) -> None:
                if int(event.chat_id or 0) != TELEGRAM_COMMUNITY_CHAT_ID: return
                try:
                    telegram_message_id = int(event.message.id)
                    async with get_session() as db:
                        part = (await db.execute(select(CommunityTelegramPart).where(CommunityTelegramPart.telegram_chat_id == TELEGRAM_COMMUNITY_CHAT_ID, CommunityTelegramPart.telegram_message_id == telegram_message_id,).options(selectinload(CommunityTelegramPart.message).selectinload(CommunityMessage.topic)))).scalar_one_or_none()
                        if part:
                            await _upsert_telethon_message(
                                db,
                                client=client,
                                topic=part.message.topic,
                                telegram_message=event.message,
                            )
                            await db.commit()
                except Exception: log.exception("telethon message edit mirror failed")

            async def handle_delete(event: Any) -> None:
                if int(event.chat_id or 0) != TELEGRAM_COMMUNITY_CHAT_ID: return
                try:
                    async with get_session() as db:
                        count = await mark_community_telegram_messages_deleted(db, list(event.deleted_ids))
                        await db.commit()
                    log.info(
                        "telethon deletion event received ids=%s matched=%s",
                        len(event.deleted_ids),
                        count,
                    )
                except Exception: log.exception("telethon message deletion mirror failed")

            client.add_event_handler(handle_edit, events.MessageEdited())
            client.add_event_handler(handle_delete, events.MessageDeleted())
            await client.catch_up()
            peer = await _resolve_forum_peer(client)
            admin_log_task = asyncio.create_task(_run_telegram_admin_log_reconciler(client, peer, stop_event))

            topic_result = await _sync_telegram_forum_topics_with_client(client)
            log.info(
                "telethon topics synchronized total=%s discovered=%s updated=%s restored=%s deleted=%s",
                topic_result.total,
                topic_result.discovered,
                topic_result.updated,
                topic_result.restored,
                topic_result.deleted,
            )
            history_result = await _sync_telegram_forum_history_with_client(client)
            log.info("telethon history synchronized %s", history_result)

            topic_interval = max(TELEGRAM_USERBOT_TOPIC_SYNC_INTERVAL_SECONDS, 60)
            history_interval = max(TELEGRAM_USERBOT_HISTORY_SYNC_INTERVAL_SECONDS, 60)
            loop = asyncio.get_running_loop()
            last_topic_sync = loop.time()
            last_history_sync = loop.time()
            while not stop_event.is_set() and client.is_connected():
                now_monotonic = loop.time()
                next_topic_in = max(topic_interval - (now_monotonic - last_topic_sync), 0.1)
                next_history_in = max(history_interval - (now_monotonic - last_history_sync), 0.1)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=min(next_topic_in, next_history_in))
                    continue
                except TimeoutError:
                    pass
                now_monotonic = loop.time()
                if now_monotonic - last_topic_sync >= topic_interval:
                    result = await _sync_telegram_forum_topics_with_client(client)
                    log.info("telethon topics reconciled total=%s", result.total)
                    last_topic_sync = now_monotonic
                if now_monotonic - last_history_sync >= history_interval:
                    result = await _sync_telegram_forum_history_with_client(client)
                    log.info("telethon history reconciled %s", result)
                    last_history_sync = now_monotonic
        except asyncio.CancelledError: raise
        except Exception:
            log.exception("telethon mirror loop failed; reconnecting")
            try: await asyncio.wait_for(stop_event.wait(), timeout=retry_seconds)
            except TimeoutError:
                pass
        finally:
            if admin_log_task is not None:
                admin_log_task.cancel()
                with suppress(asyncio.CancelledError):
                    await admin_log_task
            if client.is_connected(): await client.disconnect()
            _lock_down_session_file()
