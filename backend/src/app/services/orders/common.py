from src.normalize import normalize_phone as _normalize_phone

def _delivery_string(selected_delivery_service: str, address_str: str | None) -> str:
    service = (selected_delivery_service or "").strip().upper()
    if not service:
        return "Не указан"
    if address_str:
        return f"{service}: {address_str}"
    return service
