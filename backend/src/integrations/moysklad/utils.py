from decimal import Decimal
from typing import Any
from uuid import UUID
from config import MOY_SKLAD_PRICE_TYPE_ID, MOY_SKLAD_CURRENCY_ID

from src.normalize import coerce_decimal, coerce_uuid, fit_text, optional_str


def money(value: Any) -> Decimal:
    if value is None: return Decimal("0")
    return Decimal(str(value)) / Decimal("100")


def sale_price(item: dict[str, Any]) -> Decimal | None:
    """Select the audited retail RUB price; never infer it from array order."""
    prices = item.get("salePrices")
    if not isinstance(prices, list): return None
    def ref_id(ref):
        if not isinstance(ref, dict): return None
        return coerce_uuid(ref.get("id")) or coerce_uuid(str((ref.get("meta") or {}).get("href", "")).rstrip("/").rsplit("/", 1)[-1])
    selected = [p for p in prices if isinstance(p, dict)
                and ref_id(p.get("priceType")) == coerce_uuid(MOY_SKLAD_PRICE_TYPE_ID)
                and ref_id(p.get("currency")) == coerce_uuid(MOY_SKLAD_CURRENCY_ID)]
    if len(selected) != 1: return None
    value = coerce_decimal(selected[0].get("value"))
    if value is None or not value.is_finite() or value <= 0: return None
    return (value / 100).quantize(Decimal("0.01"))


def available_stock(value: Any, reserve: int) -> int:
    raw = max(int(coerce_decimal(value) or Decimal("0")), 0)
    return raw - reserve if reserve > 0 and raw >= reserve else raw if reserve <= 0 else 0


def assortment_id(row: dict[str, Any]) -> UUID | None:
    direct = coerce_uuid(row.get("assortmentId"))
    if direct: return direct

    assortment = row.get("assortment")
    if isinstance(assortment, dict):
        direct = coerce_uuid(assortment.get("id"))
        if direct: return direct
        href = optional_str((assortment.get("meta") or {}).get("href")) if isinstance(assortment.get("meta"), dict) else None
        if href: return coerce_uuid(href.rstrip("/").rsplit("/", 1)[-1])

    return None


def display_variant_name(value: Any, product_name: Any = None, fallback: str = "Основной вариант") -> str:
    name = optional_str(value)
    product = optional_str(product_name)
    if not name: return fallback
    if not product: return name

    n, p = name.casefold().replace("ё", "е"), product.casefold().replace("ё", "е")
    if n == p: return fallback
    if not n.startswith(p): return name

    rest = name[len(product):]
    if rest and rest[0].isalnum(): return name
    rest = rest.strip().lstrip(" \t\r\n-–—:|/\\").strip()
    if len(rest) >= 2 and rest.startswith("(") and rest.endswith(")"): rest = rest[1:-1].strip()
    return rest or fallback
