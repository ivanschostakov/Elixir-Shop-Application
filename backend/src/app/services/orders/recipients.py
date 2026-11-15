from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import (
    create_delivery_recipient,
    get_delivery_recipient_by_fields,
    get_delivery_recipient_by_id,
    get_delivery_recipients,
)
from src.database.models import DeliveryRecipient, User
from src.database.schemas import DeliveryRecipientRead

from .common import _normalize_phone
from .draft_normalization import _build_new_recipient_data


def _identity_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _identity_phone(value: str | None) -> str:
    digits = (_normalize_phone(value) or "").removeprefix("+")
    if len(digits) < 10 or not digits.isascii() or not digits.isdigit():
        return ""
    if len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    return digits


def _matches_profile(recipient, user: User, *, exact: bool) -> bool:
    if (_identity_text(recipient.name), _identity_text(recipient.surname)) != (
        _identity_text(user.name), _identity_text(user.surname)
    ):
        return False
    email = _identity_text(recipient.email)
    phone = _identity_phone(recipient.phone)
    same_email = bool(email and email == _identity_text(user.email))
    same_phone = bool(phone and phone == _identity_phone(user.phone_number))
    return (same_email and same_phone) if exact else (same_email or same_phone)


def is_profile_recipient(recipient: DeliveryRecipient | None, user: User) -> bool:
    if recipient is None:
        return False
    if recipient.is_profile_snapshot is not None:
        return recipient.is_profile_snapshot
    # Older records have no source. A shared name alone is not enough to hide one.
    return _matches_profile(recipient, user, exact=False)


def saved_checkout_recipient(recipient: DeliveryRecipient | None, user: User) -> DeliveryRecipient | None:
    return None if is_profile_recipient(recipient, user) else recipient


async def get_checkout_recipients(
    session: AsyncSession, *, user: User, selected: DeliveryRecipient | None, limit: int,
) -> list[DeliveryRecipientRead]:
    saved = await get_delivery_recipients(session, user.id, limit=limit)
    recipients = [recipient for recipient in saved if not is_profile_recipient(recipient, user)]
    if selected is not None and not is_profile_recipient(selected, user) and all(
        recipient.id != selected.id for recipient in recipients
    ):
        recipients.insert(0, selected)
    return [DeliveryRecipientRead.model_validate(recipient) for recipient in recipients]


async def resolve_checkout_recipient_selection(session: AsyncSession, *, user: User, payload) -> int | None:
    if payload.new_recipient is not None:
        if "recipient_id" in payload.model_fields_set:
            raise HTTPException(400, "Choose an existing recipient or create a new one")
        data = _build_new_recipient_data(user.id, payload.new_recipient)
        if _matches_profile(data, user, exact=True):
            return None
        recipient = await get_delivery_recipient_by_fields(
            session, user_id=data.user_id, name=data.name, surname=data.surname,
            phone=data.phone, email=data.email,
        )
        if recipient is None:
            recipient = await create_delivery_recipient(session, data, commit=False)
        return recipient.id

    if payload.recipient_id is None:
        return None
    recipient = await get_delivery_recipient_by_id(session, payload.recipient_id, user_id=user.id)
    if recipient is None:
        raise HTTPException(404, "Delivery recipient not found")
    return None if is_profile_recipient(recipient, user) else recipient.id
