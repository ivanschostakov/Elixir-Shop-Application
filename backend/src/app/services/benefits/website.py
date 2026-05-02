from decimal import Decimal
from typing import Any

from src.database.models import WebsiteCoupon, WebsiteDiscountEntitlement

from .money import estimate_discount_amount, quantize_money, total_after
from .types import ResolvedDiscountOption


def resolve_coupon_discount(coupon: WebsiteCoupon) -> tuple[str, Decimal | None, Decimal | None, str | None]:
    if coupon.discount_type == "fixed_amount" and coupon.discount_value is not None:
        return "fixed_amount", None, quantize_money(coupon.discount_value), None
    if coupon.discount_type == "percent" and coupon.discount_value is not None:
        return "percent", quantize_money(coupon.discount_value), None, None
    return "unknown", None, None, "Website coupon exists, but its numeric discount value was not exposed by the website payload"


def resolve_entitlement_discount(entitlement: WebsiteDiscountEntitlement) -> tuple[str, Decimal | None, Decimal | None, str | None]:
    if entitlement.discount_percent is not None: return "percent", quantize_money(entitlement.discount_percent), None, None
    if entitlement.discount_amount is not None: return "fixed_amount", None, quantize_money(entitlement.discount_amount), None
    return "unknown", None, None, "Website personal discount exists, but its numeric value was not exposed by the website payload"


def build_website_coupon_option(coupon: WebsiteCoupon, *, subtotal: Decimal) -> ResolvedDiscountOption:
    calculation_mode, discount_percent, discount_amount, reason = resolve_coupon_discount(coupon)
    status = "available"
    is_applicable = True
    if calculation_mode == "unknown":
        status = "unsupported"
        is_applicable = False

    elif not coupon.is_active:
        status = "inactive"
        is_applicable = False
        reason = "Coupon is not active on the website"

    elif coupon.max_use is not None and 0 < coupon.max_use <= coupon.use_count:
        status = "usage_limit_reached"
        is_applicable = False
        reason = "Coupon usage limit has already been reached on the website"

    estimated_discount_amount = None
    if is_applicable: estimated_discount_amount = estimate_discount_amount(subtotal=subtotal, calculation_mode=calculation_mode, discount_percent=discount_percent, discount_amount=discount_amount)

    return ResolvedDiscountOption(
        source_kind="website_coupon",
        source_record_id=coupon.id,
        code=coupon.coupon_code,
        title=coupon.discount_rule_name or coupon.coupon_code,
        status=status,
        is_applicable=is_applicable,
        is_personal=False,
        is_stackable=False,
        calculation_mode=calculation_mode,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        currency=coupon.discount_currency,
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=total_after(subtotal, estimated_discount_amount),
        reason=reason,
    )


def build_website_entitlement_option(entitlement: WebsiteDiscountEntitlement, *, subtotal: Decimal, now: Any) -> ResolvedDiscountOption:
    calculation_mode, discount_percent, discount_amount, reason = resolve_entitlement_discount(entitlement)
    status = "available"
    is_applicable = True
    if calculation_mode == "unknown":
        status = "unsupported"
        is_applicable = False

    elif not entitlement.is_active:
        status = "inactive"
        is_applicable = False
        reason = "Website personal discount is not active"

    elif entitlement.starts_at and entitlement.starts_at > now:
        status = "scheduled"
        is_applicable = False
        reason = "Website personal discount is not active yet"

    elif entitlement.ends_at and entitlement.ends_at < now:
        status = "expired"
        is_applicable = False
        reason = "Website personal discount has expired"

    estimated_discount_amount = None
    if is_applicable: estimated_discount_amount = estimate_discount_amount(subtotal=subtotal, calculation_mode=calculation_mode, discount_percent=discount_percent, discount_amount=discount_amount)

    return ResolvedDiscountOption(
        source_kind="website_discount_entitlement",
        source_record_id=entitlement.id,
        code=None,
        title=entitlement.source_name,
        status=status,
        is_applicable=is_applicable,
        is_personal=True,
        is_stackable=entitlement.is_stackable,
        calculation_mode=calculation_mode,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        currency=entitlement.currency,
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=total_after(subtotal, estimated_discount_amount),
        reason=reason,
    )
