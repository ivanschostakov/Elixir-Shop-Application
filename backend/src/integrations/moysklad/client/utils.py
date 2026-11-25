from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
from math import isfinite
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from src.normalize import coerce_uuid, optional_str
from .common import CUSTOMER_ORDER_ATTR_IDS, MOY_SKLAD_API_BASE_URL


def custom_entity_dictionary_id(attribute: dict[str, Any]) -> UUID | None:
    meta = attribute.get("customEntityMeta")
    href = meta.get("href") if isinstance(meta, dict) else None
    if not isinstance(href, str) or not href.strip():
        return None
    path = urlsplit(href).path.rstrip("/").removesuffix("/metadata").split("/")
    if len(path) < 3 or path[-3:-1] != ["entity", "customentity"]:
        return None
    return coerce_uuid(path[-1])


def _customer_order_attr_id(attr_key: str) -> str:
    attr_id = CUSTOMER_ORDER_ATTR_IDS.get(attr_key)
    if not attr_id: raise KeyError(f"Unknown customer order attribute key: {attr_key}")
    return attr_id


def attr_meta(attr_key: str) -> dict[str, Any]:
    return {"meta": {"href": f"{MOY_SKLAD_API_BASE_URL}/entity/customerorder/metadata/attributes/{_customer_order_attr_id(attr_key)}", "type": "attributemetadata", "mediaType": "application/json"}}


def order_attr(attr_key: str, value: Any) -> dict[str, Any]:
    payload = attr_meta(attr_key)
    payload["value"] = value
    return payload


def custom_order_attr(attr_key: str, value_href: str) -> dict[str, Any]:
    href = optional_str(value_href)
    if not href: raise ValueError(f"Customer order customentity attribute {attr_key} expects a non-empty href")
    return order_attr(attr_key, {"meta": {"href": href, "type": "customentity", "mediaType": "application/json"}})


def entity_ref(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta") if isinstance(row, dict) else None
    if not isinstance(meta, dict): raise RuntimeError("MoySklad entity row is missing meta")
    return {"meta": meta}


def moysklad_money(amount: Decimal) -> int:
    return int((Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def moysklad_retry_after_seconds(response: httpx.Response, *, default: float) -> float:
    try:
        lognex_delay = float(response.headers.get("X-Lognex-Retry-After", "0")) / 1000
        retry_after = response.headers.get("Retry-After", "0")
        try:
            delay = float(retry_after)
        except ValueError:
            at = parsedate_to_datetime(retry_after)
            delay = (at - datetime.now(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return max(60, default)
    if not isfinite(lognex_delay) or not isfinite(delay):
        return max(60, default)
    return max(default, lognex_delay, delay)
