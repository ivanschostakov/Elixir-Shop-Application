from decimal import Decimal
from typing import Any
from uuid import UUID

from src.normalize import coerce_decimal, coerce_uuid, fit_text, optional_str


def money(value: Any) -> Decimal:
    if value is None: return Decimal("0")
    return Decimal(str(value)) / Decimal("100")


def sale_price(item: dict[str, Any]) -> Decimal:
    prices = item.get("salePrices")
    if not isinstance(prices, list) or not prices or not isinstance(prices[0], dict): return Decimal("0")
    return money(prices[0].get("value"))


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