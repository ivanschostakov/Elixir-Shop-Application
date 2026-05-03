import hashlib
import json

from decimal import Decimal
from typing import Any

import httpx


def as_str(value: Any) -> str:
    if value is None: return ""
    if isinstance(value, Decimal): return f"{value:.2f}"
    return str(value)


def sha256_signature(*parts: Any) -> str:
    raw = "::".join(as_str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def md5_hash(*parts: Any) -> str:
    raw = "::".join(as_str(part) for part in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def md5_hash_encoded(*parts: Any, encoding: str = "utf-8") -> str | None:
    raw = "::".join(as_str(part) for part in parts)
    try: return hashlib.md5(raw.encode(encoding)).hexdigest()
    except UnicodeEncodeError: return None


def amount(value: Decimal | float | int | str) -> str:
    return f"{Decimal(str(value)):.2f}"


def is_hash_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "param: hash" in text or '"hash"' in text


def safe_form_value_for_log(key: str, value: Any) -> str:
    normalized_key = str(key).lower()
    if normalized_key in {"hash", "secretkey"} or "token" in normalized_key or "secret" in normalized_key: return "<redacted>" if value else ""
    if normalized_key in {"email", "useremail"}:
        raw = str(value or "")
        if "@" not in raw: return "<masked>" if raw else ""
        local, domain = raw.split("@", 1)
        local_mask = f"{local[:2]}***" if len(local) > 2 else "***"
        return f"{local_mask}@{domain}"

    return str(value)


def safe_form_for_log(form_data: dict[str, Any]) -> dict[str, str]: return {str(key): safe_form_value_for_log(str(key), value) for key, value in sorted(form_data.items())}
def response_body_for_log(response: httpx.Response) -> str:
    try: return response.text
    except UnicodeDecodeError: return response.content.decode("utf-8", "replace")


def webhook_payload_value(payload: dict[str, Any], key: str) -> Any:
    if key in payload: return payload.get(key)
    normalized_key = key.lower()
    for payload_key, value in payload.items():
        if str(payload_key).lower() == normalized_key: return value
    return None


def parse_payment_state(data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("Result") or {}
    payment_step = str(result.get("PaymentStep") or "")
    form_3ds_raw = result.get("Form3DS") or ""
    form_3ds: dict[str, Any] = {}
    if isinstance(form_3ds_raw, str) and form_3ds_raw.strip():
        try: form_3ds = json.loads(form_3ds_raw)
        except json.JSONDecodeError: form_3ds = {}

    return {
        "payment_step": payment_step,
        "qr_url": form_3ds.get("SbpQrCodeUrl"),
        "qr_image": form_3ds.get("SbpQrCodeImage"),
    }
