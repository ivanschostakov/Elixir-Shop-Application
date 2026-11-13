import re

from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError

_EMAIL = TypeAdapter(EmailStr)


def _normalize_phone(phone: str | None) -> str | None:
    if phone is None: return None
    normalized = re.sub(r"[\s()-]", "", str(phone).strip())
    return normalized or None


def _require_recipient_phone(phone: str | None) -> str:
    normalized = _normalize_phone(phone)
    if not normalized or not re.fullmatch(r"\+?[0-9]{10,15}", normalized):
        raise HTTPException(status_code=422, detail="Укажите корректный телефон получателя (от 10 до 15 цифр)")
    return normalized


def validate_checkout_recipient(recipient) -> None:
    normalized_phone = _require_recipient_phone(recipient.phone)
    for field, label in (("name", "имя"), ("surname", "фамилию")):
        if not (getattr(recipient, field) or "").strip():
            raise HTTPException(422, f"Укажите {label} получателя")
    try:
        _EMAIL.validate_python(recipient.email)
    except ValidationError as exc:
        raise HTTPException(422, "Укажите корректный email получателя") from exc
    recipient.phone = normalized_phone


def _delivery_string(selected_delivery_service: str, address_str: str | None) -> str:
    service = (selected_delivery_service or "").strip().upper()
    if not service: return "Не указан"
    if address_str: return f"{service}: {address_str}"
    return service
