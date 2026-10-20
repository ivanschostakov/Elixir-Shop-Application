from typing import Any

from .constants import MAX_CONTENT_LENGTH


def _content(value: Any) -> str | None:
    if value is None: return None
    if not isinstance(value, str): raise ValueError("Catalog content fields must be strings or null")
    normalized = value.replace("\x00", "").strip()
    if not normalized: return None
    if len(normalized) > MAX_CONTENT_LENGTH: raise ValueError("Catalog content field is too long")
    return normalized


def _sku(value: Any) -> str | None:
    if not isinstance(value, str): return None
    normalized = value.replace("\x00", "").strip().casefold()
    return normalized[:256] or None


def _short_text(value: Any, *, max_length: int, required: bool = False) -> str | None:
    if value is None:
        if required: raise ValueError("Required catalog text field is missing")
        return None
    
    if not isinstance(value, str): raise ValueError("Catalog text fields must be strings or null")
    
    normalized = value.replace("\x00", "").strip()
    if not normalized:
        if required: raise ValueError("Required catalog text field is empty")
        return None
    
    if len(normalized) > max_length: raise ValueError("Catalog text field is too long")
    return normalized


def _category_name_key(value: str) -> str:
    return " ".join(value.split()).casefold()
