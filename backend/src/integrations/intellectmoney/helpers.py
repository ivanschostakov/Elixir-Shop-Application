import hashlib
import json

from decimal import Decimal
from typing import Any

import httpx

MAX_LOG_STRING_LENGTH = 1024
MAX_LOG_LIST_ITEMS = 20


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


def _truncate_text(value: str, *, max_length: int = MAX_LOG_STRING_LENGTH) -> str:
    if len(value) <= max_length:
        return value
    trimmed = value[:max_length]
    return f"{trimmed}...<truncated {len(value) - max_length} chars>"


def _redacted_blob_summary(value: Any) -> str:
    raw = str(value or "")
    return f"<redacted len={len(raw)}>"


def _sanitize_for_log(value: Any, key: str | None = None) -> Any:
    normalized_key = (key or "").strip().lower()

    if normalized_key in {"sbpqrcodeimage", "qr_image"}:
        return _redacted_blob_summary(value)

    if normalized_key == "form3ds":
        raw = str(value or "")
        if not raw:
            return ""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return _truncate_text(raw)
        return _sanitize_for_log(parsed, key="form3ds_payload")

    if isinstance(value, dict):
        return {
            str(item_key): _sanitize_for_log(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        sanitized_items = [
            _sanitize_for_log(item)
            for item in value[:MAX_LOG_LIST_ITEMS]
        ]
        if len(value) > MAX_LOG_LIST_ITEMS:
            sanitized_items.append(f"<truncated {len(value) - MAX_LOG_LIST_ITEMS} items>")
        return sanitized_items

    if isinstance(value, str):
        return _truncate_text(value)

    return value


def response_body_for_log(response: httpx.Response) -> str:
    try:
        payload = response.json()
        sanitized_payload = _sanitize_for_log(payload)
        return json.dumps(sanitized_payload, ensure_ascii=False)
    except ValueError:
        pass

    try:
        return _truncate_text(response.text)
    except UnicodeDecodeError:
        return _truncate_text(response.content.decode("utf-8", "replace"))


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
