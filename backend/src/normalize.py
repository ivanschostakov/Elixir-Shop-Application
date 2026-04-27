import math
import re
import uuid

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from pydantic import EmailStr, TypeAdapter

from config import UFA_TZ
from src.database.limits import EMAIL_MAX_LENGTH, USERNAME_MAX_LENGTH

EMAIL_ADAPTER = TypeAdapter(EmailStr)


def optional_str(value: Any) -> str | None:
    if value is None: return None
    if isinstance(value, float) and math.isnan(value): return None
    normalized = str(value).strip()
    return normalized or None


def lower_optional_str(value: Any) -> str | None:
    normalized = optional_str(value)
    return normalized.lower() if normalized else None


def casefold_optional_str(value: Any) -> str | None:
    normalized = optional_str(value)
    return normalized.casefold() if normalized else None


def non_empty_str_list(values: Iterable[Any] | None) -> list[str]:
    if values is None or isinstance(values, (str, bytes, dict)): return []

    normalized_values: list[str] = []
    for item in values:
        normalized = optional_str(item)
        if normalized: normalized_values.append(normalized)
    return normalized_values


def fit_text(value: Any, max_length: int) -> str | None:
    normalized = optional_str(value)
    if normalized is None: return None
    return normalized[:max_length]


def normalize_person_name(value: Any, *, max_length: int | None = None) -> str | None:
    normalized = optional_str(value)
    if normalized is None:
        return None

    normalized = re.sub(r"\s+", " ", normalized).title()
    if max_length is not None:
        return normalized[:max_length]
    return normalized


def normalize_email(value: Any) -> str | None:
    normalized = optional_str(value)
    if not normalized: return None
    try: validated = EMAIL_ADAPTER.validate_python(normalized)
    except Exception: return None
    return str(validated).lower()[:EMAIL_MAX_LENGTH]


def normalize_phone(value: Any) -> str | None:
    normalized = optional_str(value)
    if normalized is None: return None
    normalized = re.sub(r"[\s()-]", "", normalized)
    return normalized or None


def parse_iso_datetime(value: Any) -> datetime | None:
    normalized = optional_str(value)
    if not normalized: return None
    try: parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError: return None

    if parsed.tzinfo is None: return parsed.replace(tzinfo=UFA_TZ)
    return parsed


def coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None: return None
    if isinstance(value, int): return value
    normalized = optional_str(value)
    if not normalized: return None
    try: return int(normalized)
    except ValueError: return None


def coerce_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None: return None
    if isinstance(value, Decimal): return value
    if isinstance(value, int): return Decimal(value)
    if isinstance(value, float): return Decimal(str(value))

    normalized = optional_str(value)
    if not normalized: return None
    if "|" in normalized: normalized = normalized.split("|", 1)[0]
    normalized = normalized.replace(",", ".")
    try: return Decimal(normalized)
    except (InvalidOperation, ValueError): return None


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool): return value
    if value is None: return None
    normalized = lower_optional_str(value)
    if not normalized: return None
    if normalized in {"1", "y", "yes", "true"}: return True
    if normalized in {"0", "n", "no", "false"}: return False
    return None


def coerce_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID): return value
    normalized = optional_str(value)
    if normalized is None: return None
    try: return uuid.UUID(normalized)
    except (ValueError, TypeError): return None


def extract_money(value: Any) -> tuple[Decimal | None, str | None]:
    if isinstance(value, dict):
        amount = coerce_decimal(value.get("amount"))
        currency = optional_str(value.get("currency"))
        if amount is None:
            raw = optional_str(value.get("raw"))
            if raw and "|" in raw:
                raw_amount, raw_currency = raw.split("|", 1)
                amount = coerce_decimal(raw_amount)
                currency = currency or optional_str(raw_currency)
        return amount, currency

    raw = optional_str(value)
    if raw and "|" in raw:
        raw_amount, raw_currency = raw.split("|", 1)
        return coerce_decimal(raw_amount), optional_str(raw_currency)
    return coerce_decimal(value), None


def extract_dict(value: Any) -> dict[str, Any]: return value if isinstance(value, dict) else {}
def normalize_username(value: Any, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", lower_optional_str(value) or "").strip("_")
    normalized = normalized or fallback
    return normalized[:USERNAME_MAX_LENGTH] or fallback[:USERNAME_MAX_LENGTH]

def is_valid_uuid(s: str) -> bool:
    try: return uuid.UUID(s) is not None
    except (ValueError, TypeError, AttributeError): return False
