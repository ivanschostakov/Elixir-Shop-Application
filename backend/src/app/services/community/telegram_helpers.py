from typing import Any
from src.database.models import CommunityMessage, CommunityTopic, User
from src.integrations.telegram import TelegramBotAPIError, TelegramBotClient


async def _reply_parameters(message: CommunityMessage) -> dict[str, Any] | None:
    if not message.reply_to: return None
    active_parts = [part for part in message.reply_to.telegram_parts if part.deleted_at is None]
    if not active_parts: return None
    return {"message_id": active_parts[0].telegram_message_id, "allow_sending_without_reply": True}


def _telegram_text_chunks(value: str, limit: int = 4096) -> list[str]:
    remaining = value.strip()
    chunks: list[str] = []
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = max(remaining.rfind("\n", 0, limit + 1), remaining.rfind(" ", 0, limit + 1))
        if split_at < limit // 2: split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    return chunks


def _telegram_app_header(message: CommunityMessage) -> tuple[str, str]:
    author_name = message.author.full_name if message.author else "Elixir member"
    message_kind = "↩️" if message.reply_to else "💬"
    return author_name, f"{author_name} · {message_kind} Приложение"


def _telegram_app_reaction_notification(user: User, emoji: str) -> tuple[str, str]:
    author_name = " ".join(part for part in (str(user.name or "").strip(), str(user.surname or "").strip()) if part) or "Elixir member"
    return author_name, f"{author_name} · ↩️ Приложение\n\nОтреагировал(а) {emoji}"


def _telegram_bot_thread_id(topic: CommunityTopic) -> int | None:
    thread_id = int(topic.telegram_thread_id or 0)
    # Telegram's non-deletable General topic has MTProto id=1, but Bot API
    # messages reach it by omitting message_thread_id.
    return thread_id if thread_id > 1 else None


def _is_telegram_app_reaction_notification(value: str) -> bool:
    header, separator, body = value.strip().partition("\n\n")
    return bool(separator and header.endswith(" · ↩️ Приложение") and body.strip().startswith("Отреагировал(а) "))


def _telegram_author_entities(value: str, author_name: str) -> list[dict[str, Any]]:
    if not author_name or not value.startswith(author_name): return []
    # Telegram entity offsets and lengths use UTF-16 code units.
    author_length = len(author_name.encode("utf-16-le")) // 2
    return [{"type": "bold", "offset": 0, "length": author_length}]


def _telegram_message_is_already_absent(exc: TelegramBotAPIError) -> bool:
    message = str(exc).casefold()
    return exc.error_code == 400 and "message to delete not found" in message


def _telegram_retry_delay_seconds(delivery_attempts: int, *, retry_after: int | None = None) -> int:
    if retry_after is not None: return max(int(retry_after), 1)
    exponent = min(max(int(delivery_attempts) - 1, 0), 6)
    return min(300, 5 * (2 ** exponent))


async def _delete_telegram_message_ids(telegram_client: TelegramBotClient, *, chat_id: int, message_ids: list[int],) -> None:
    normalized_ids = sorted({int(message_id) for message_id in message_ids if int(message_id) > 0})
    for offset in range(0, len(normalized_ids), 100):
        chunk = normalized_ids[offset:offset + 100]
        try:
            await telegram_client.call(
                "deleteMessages",
                data={"chat_id": chat_id, "message_ids": chunk},
            )
        except TelegramBotAPIError:
            # A stale ID can make the bulk request fail. Retry individually so
            # valid tracked replies are still cleaned up.
            for telegram_message_id in chunk:
                try:
                    await telegram_client.call(
                        "deleteMessage",
                        data={"chat_id": chat_id, "message_id": telegram_message_id},
                    )
                except TelegramBotAPIError as exc:
                    if not _telegram_message_is_already_absent(exc): raise
