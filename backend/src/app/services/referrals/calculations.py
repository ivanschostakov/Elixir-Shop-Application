from decimal import ROUND_HALF_UP, Decimal

from src.normalize import optional_str

MONEY_QUANTIZER = Decimal("0.01")
MIN_PARTICIPANT_DISCOUNT_PERCENT = Decimal("3.00")
MAX_PERSONAL_DISCOUNT_PERCENT = Decimal("20.00")
OWN_PROMO_PURCHASE_THRESHOLD = Decimal("100000.00")
REFERRER_ELIGIBLE_PURCHASE_THRESHOLD = Decimal("100000.00")
MONTHLY_COMMISSION_ACTIVITY_THRESHOLD = Decimal("10000.00")
KIPARIS_CODE = "КИПАРИС"


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def quantize_percent(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_personal_discount_percent(purchase_total: Decimal | int | float | str | None, *, has_referrer: bool) -> Decimal:
    if not has_referrer:
        return Decimal("0.00")

    total = quantize_money(purchase_total)
    stepped_percent = Decimal(max(3, int(total // Decimal("10000.00"))))
    return min(MAX_PERSONAL_DISCOUNT_PERCENT, stepped_percent).quantize(Decimal("0.01"))


def is_kiparis_code(code: str | None) -> bool:
    normalized = optional_str(code)
    return bool(normalized and normalized.casefold() == KIPARIS_CODE.casefold())


def calculate_level_one_commission_percent(*, referrer_discount_percent: Decimal | int | float | str | None, referral_discount_percent: Decimal | int | float | str | None, promo_code: str | None) -> Decimal:
    referrer_percent = quantize_percent(referrer_discount_percent)
    referral_percent = quantize_percent(referral_discount_percent)

    if is_kiparis_code(promo_code) and referral_percent >= Decimal("12.00"):
        return Decimal("0.00")

    if referral_percent >= MAX_PERSONAL_DISCOUNT_PERCENT:
        return Decimal("3.00")

    return max(Decimal("0.00"), referrer_percent - referral_percent).quantize(Decimal("0.01"))


def calculate_super_referrer_commission_percent() -> Decimal:
    return Decimal("3.00")


def calculate_commission_amount(order_subtotal: Decimal | int | float | str | None, commission_percent: Decimal | int | float | str | None) -> Decimal:
    subtotal = quantize_money(order_subtotal)
    percent = quantize_percent(commission_percent)
    return quantize_money(subtotal * percent / Decimal("100.00"))
