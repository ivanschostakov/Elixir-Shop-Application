import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.auth import link_telegram_contact_to_user
from src.database.crud.webhooks import payload_digest, register_webhook_delivery
from src.integrations.moysklad import MoySkladClient, get_moysklad_client

log = logging.getLogger(__name__)


def _payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


async def process_telegram_update(
    db: AsyncSession,
    payload: dict[str, Any],
    moysklad_client: MoySkladClient | None = None,
) -> dict[str, Any]:
    delivery_id = str(payload.get("update_id") or "").strip() or None
    accepted = await register_webhook_delivery(
        db,
        provider="telegram",
        delivery_id=delivery_id,
        payload_hash=payload_digest(_payload_bytes(payload)),
    )
    if not accepted:
        return {"ok": True, "ignored": "duplicate"}

    message = payload.get("message")
    if not isinstance(message, dict):
        return {"ok": True, "ignored": "no message"}

    contact = message.get("contact")
    sender = message.get("from")
    if not isinstance(contact, dict) or not isinstance(sender, dict):
        return {"ok": True, "ignored": "no contact"}

    try:
        contact_user_id = int(contact.get("user_id") or 0)
        sender_user_id = int(sender.get("id") or 0)
    except (TypeError, ValueError):
        return {"ok": True, "ignored": "invalid contact user"}
    if contact_user_id <= 0 or contact_user_id != sender_user_id:
        return {"ok": True, "ignored": "contact does not belong to sender"}

    user, reason = await link_telegram_contact_to_user(
        db,
        telegram_user_id=contact_user_id,
        phone_number=str(contact.get("phone_number") or ""),
        first_name=contact.get("first_name") or sender.get("first_name"),
        last_name=contact.get("last_name") or sender.get("last_name"),
        username=sender.get("username"),
        moysklad_client=moysklad_client or get_moysklad_client(),
    )
    if user is None:
        return {"ok": True, "ignored": reason or "contact not linked"}

    moysklad_counterparty_id = (
        str(user.moysklad_counterparty_id)
        if user.moysklad_counterparty_id is not None
        else None
    )
    log.info(
        "telegram contact linked user_id=%s telegram_user_id=%s moysklad_counterparty_id=%s",
        user.id,
        contact_user_id,
        moysklad_counterparty_id,
    )
    return {"ok": True, "user_id": user.id}
