from decimal import ROUND_HALF_UP, Decimal

MONEY_QUANTIZER = Decimal("0.01")
MIN_PARTICIPANT_DISCOUNT_PERCENT = Decimal("3.00")
MAX_PERSONAL_DISCOUNT_PERCENT = Decimal("17.00")
PERSONAL_DISCOUNT_STEP_SPEND = Decimal("10000.00")


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def quantize_percent(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_personal_discount_percent(
    purchase_total: Decimal | int | float | str | None,
    *,
    has_promo_code: bool | None = None,
    has_referrer: bool | None = None,
) -> Decimal:
    eligible = has_promo_code if has_promo_code is not None else has_referrer
    if not eligible:
        return Decimal("0.00")

    total = quantize_money(purchase_total)
    stepped_percent = Decimal(max(3, int(total // PERSONAL_DISCOUNT_STEP_SPEND)))
    return min(MAX_PERSONAL_DISCOUNT_PERCENT, stepped_percent).quantize(Decimal("0.01"))
