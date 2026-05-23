import re


def _normalize_phone(phone: str | None) -> str | None:
    if phone is None: return None
    normalized = re.sub(r"[\s()-]", "", str(phone).strip())
    return normalized or None


def _delivery_string(selected_delivery_service: str, address_str: str | None) -> str:
    service = (selected_delivery_service or "").strip().upper()
    if not service: return "Не указан"
    if address_str: return f"{service}: {address_str}"
    return service
