from src.database.models import Order, User
from src.normalize import optional_str


def _full_name(user: User, order: Order) -> str:
    recipient = order.recipient
    parts = [
        optional_str(recipient.name) if recipient is not None else None,
        optional_str(recipient.surname) if recipient is not None else None,
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name: return full_name

    fallback_parts = [optional_str(user.name), optional_str(user.surname)]
    fallback_name = " ".join(part for part in fallback_parts if part)
    if fallback_name: return fallback_name

    email_fallback = optional_str(user.email)
    if email_fallback: return email_fallback
    return f"User {user.__dict__.get('id') or 'unknown'}"


def _counterparty_email(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_email = optional_str(recipient.email)
        if recipient_email: return recipient_email

    return optional_str(user.email)


def _counterparty_phone(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_phone = optional_str(recipient.phone)
        if recipient_phone: return recipient_phone

    return optional_str(user.phone_number)


def _counterparty_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        address = optional_str(order.delivery_address.full_address)
        if address: return address

    return optional_str(order.delivery_string)
