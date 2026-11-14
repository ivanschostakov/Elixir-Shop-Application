from src.database.models import Order, User
from src.integrations.amocrm.utils import normalize_phone
from src.normalize import optional_str


def _full_name(user: User, order: Order) -> str:
    fallback_parts = [optional_str(user.name), optional_str(user.surname)]
    fallback_name = " ".join(part for part in fallback_parts if part)
    if fallback_name: return fallback_name

    recipient = order.recipient
    parts = [
        optional_str(recipient.name) if recipient is not None else None,
        optional_str(recipient.surname) if recipient is not None else None,
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name: return full_name

    email_fallback = optional_str(user.email)
    if email_fallback: return email_fallback
    return f"User {user.__dict__.get('id') or 'unknown'}"


def _counterparty_email(user: User, order: Order) -> str | None:
    recipient = order.recipient
    email = optional_str(user.email)
    if email or recipient is None: return email
    buyer_phone = normalize_phone(user.phone_number)
    return optional_str(recipient.email) if buyer_phone and buyer_phone == normalize_phone(recipient.phone) else None


def _counterparty_phone(user: User, order: Order) -> str | None:
    recipient = order.recipient
    phone = optional_str(user.phone_number)
    if phone or recipient is None: return phone
    email = optional_str(user.email)
    return optional_str(recipient.phone) if email and email.casefold() == (recipient.email or "").strip().casefold() else None


def _counterparty_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        address = optional_str(order.delivery_address.full_address)
        if address: return address

    return optional_str(order.delivery_string)
