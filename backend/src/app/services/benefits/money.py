from decimal import ROUND_HALF_UP, Decimal

from src.normalize import optional_str

from .types import ResolvedDiscountOption

MONEY_QUANTIZER = Decimal("0.01")


def quantize_money(value: Decimal | int | float | None) -> Decimal | None:
    if value is None: return None
    return Decimal(str(value)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def percent_to_amount(subtotal: Decimal, percent: Decimal | None) -> Decimal | None:
    if percent is None: return None
    return quantize_money(subtotal * percent / Decimal("100"))


def fixed_to_amount(subtotal: Decimal, amount: Decimal | None) -> Decimal | None:
    if amount is None: return None
    return min(subtotal, quantize_money(amount) or Decimal("0.00"))


def estimate_discount_amount(*, subtotal: Decimal, calculation_mode: str, discount_percent: Decimal | None, discount_amount: Decimal | None) -> Decimal | None:
    if calculation_mode == "percent": return percent_to_amount(subtotal, discount_percent)
    if calculation_mode == "fixed_amount": return fixed_to_amount(subtotal, discount_amount)
    return None


def total_after(subtotal: Decimal, discount_amount: Decimal | None) -> Decimal | None:
    if discount_amount is None: return None
    return quantize_money(max(Decimal("0.00"), subtotal - discount_amount))


def preferred_currency(*, requested_currency: str | None, available_options: list[ResolvedDiscountOption]) -> str | None:
    normalized_requested_currency = optional_str(requested_currency)
    if normalized_requested_currency: return normalized_requested_currency
    for option in available_options:
        if option.currency: return option.currency

    return None
