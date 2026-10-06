import re

from fastapi import HTTPException


def _normalize_phone(phone: str | None) -> str | None:
    if phone is None: return None
    normalized = re.sub(r"[\s()-]", "", str(phone).strip())
    return normalized or None


def _require_recipient_phone(phone: str | None) -> str:
    normalized = _normalize_phone(phone)
    if not normalized or not re.fullmatch(r"\+?[0-9]{7,15}", normalized):
        raise HTTPException(status_code=422, detail="Укажите корректный телефон получателя (от 7 до 15 цифр)")
    return normalized


def _delivery_string(selected_delivery_service: str, address_str: str | None) -> str:
    service = (selected_delivery_service or "").strip().upper()
    if not service: return "Не указан"
    if address_str: return f"{service}: {address_str}"
    return service
