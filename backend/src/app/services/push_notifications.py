import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config import EXPO_PUSH_API_URL, EXPO_PUSH_TIMEOUT_SECONDS
from src.database.crud import delete_user_push_token, get_user_push_tokens
from src.database.models import Order
from src.database.models.orders.history import get_order_history_bucket, get_order_status_code, normalize_order_status

log = logging.getLogger(__name__)

ORDER_STATUS_NOTIFICATION_BODIES = {
    "created": "Заказ создан. Мы уже взяли его в работу.",
    "invoice_sent": "Ожидаем оплату по заказу.",
    "paid": "Оплату получили. Спасибо за заказ.",
    "waiting_response": "Заказ уже обрабатывается.",
    "packaged": "Заказ упакован и готовится к отправке.",
    "sent": "Заказ передан в доставку.",
    "delivered": "Заказ доставлен.",
    "canceled": "Заказ отменен.",
    "completed": "Заказ завершен.",
    "refund_declined": "Возврат по заказу отклонен.",
}


def _build_order_status_body(order: Order) -> str:
    status_code = get_order_status_code(order)
    return ORDER_STATUS_NOTIFICATION_BODIES.get(status_code, f"Новый статус заказа: {order.status}")


def _build_order_status_data(order: Order) -> dict[str, Any]:
    return {
        "type": "order_status_changed",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "status_code": get_order_status_code(order),
        "history_bucket": get_order_history_bucket(order),
    }


def _build_push_messages(
    push_tokens,
    *,
    title: str,
    body: str,
    data: dict[str, Any],
    channel_id: str = "default",
) -> list[dict[str, Any]]:
    return [
        {
            "to": push_token.expo_push_token,
            "title": title,
            "body": body,
            "data": data,
            "sound": "default",
            "channelId": channel_id,
        }
        for push_token in push_tokens
    ]


async def _send_expo_push_messages(messages: list[dict[str, Any]]) -> set[str]:
    if not messages:
        return set()

    async with httpx.AsyncClient(timeout=EXPO_PUSH_TIMEOUT_SECONDS) as client:
        response = await client.post(
            EXPO_PUSH_API_URL,
            json=messages,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()

    invalid_tokens: set[str] = set()
    tickets = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(tickets, list):
        return invalid_tokens

    for message, ticket in zip(messages, tickets, strict=False):
        if not isinstance(ticket, dict):
            continue
        details = ticket.get("details")
        error_code = details.get("error") if isinstance(details, dict) else None
        if error_code == "DeviceNotRegistered":
            token = message.get("to")
            if isinstance(token, str):
                invalid_tokens.add(token)
            continue

        if ticket.get("status") == "error":
            log.warning("Expo push notification error: %s", ticket)

    return invalid_tokens


async def _delete_invalid_push_tokens(session: AsyncSession, *, push_tokens, invalid_tokens: set[str]) -> None:
    if not invalid_tokens:
        return

    removed_any = False
    for push_token in push_tokens:
        if push_token.expo_push_token not in invalid_tokens:
            continue
        await delete_user_push_token(session, push_token, commit=False)
        removed_any = True

    if removed_any:
        await session.commit()


async def send_push_to_user(
    session: AsyncSession,
    *,
    user_id: int,
    title: str,
    body: str,
    data: dict[str, Any],
    channel_id: str = "default",
) -> bool:
    push_tokens = await get_user_push_tokens(session, user_id=user_id)
    if not push_tokens:
        return False

    messages = _build_push_messages(
        push_tokens,
        title=title,
        body=body,
        data=data,
        channel_id=channel_id,
    )
    invalid_tokens = await _send_expo_push_messages(messages)
    await _delete_invalid_push_tokens(session, push_tokens=push_tokens, invalid_tokens=invalid_tokens)
    return True


async def send_order_status_change_notification(session: AsyncSession, order: Order) -> None:
    try:
        await send_push_to_user(
            session,
            user_id=order.user_id,
            title=f"Заказ №{order.order_number}",
            body=_build_order_status_body(order),
            data=_build_order_status_data(order),
        )
    except Exception:
        return log.exception("Failed to send order status notification for order %s", order.order_number)

    return None


async def send_order_status_change_notification_if_needed(
    session: AsyncSession,
    *,
    previous_status: str | None,
    order: Order,
) -> None:
    if normalize_order_status(previous_status) == normalize_order_status(order.status):
        return
    await send_order_status_change_notification(session, order)
