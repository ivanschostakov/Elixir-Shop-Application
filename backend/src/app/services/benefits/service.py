from dataclasses import asdict
from decimal import Decimal
import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.discounts import product_is_discountable
from src.app.services.referrals import attach_referrer_code, get_or_create_referral_profile, refresh_profile_discount_from_moysklad, user_has_promo_code
from src.app.services.referrals.calculations import calculate_personal_discount_percent
from src.database.crud import get_basket_by_user_id
from src.database.models import ReferralProfile, User
from src.integrations.bitrix_promo import BitrixPromoIntegrationError, bitrix_promo_client
from src.normalize import lower_optional_str, optional_str

from .money import estimate_discount_amount, preferred_currency, quantize_money
from .options import best_option_key, serialize_options
from .types import ResolvedDiscountOption

logger = logging.getLogger(__name__)


async def _resolve_subtotals(
    db: AsyncSession,
    *,
    user_id: int,
    explicit_subtotal: Decimal | None,
    explicit_discountable_subtotal: Decimal | None,
) -> tuple[Decimal, Decimal, str]:
    basket = await get_basket_by_user_id(db, user_id)
    if explicit_subtotal is not None:
        subtotal = quantize_money(explicit_subtotal) or Decimal("0.00")
        discountable_subtotal = quantize_money(explicit_discountable_subtotal) if explicit_discountable_subtotal is not None else None
        if discountable_subtotal is None and basket is not None:
            basket_subtotal, basket_discountable_subtotal = _basket_subtotals(basket)
            if basket_subtotal == subtotal:
                discountable_subtotal = basket_discountable_subtotal
        if discountable_subtotal is None:
            discountable_subtotal = subtotal
        return subtotal, min(subtotal, discountable_subtotal or Decimal("0.00")), "request"

    if basket is None: return Decimal("0.00"), Decimal("0.00"), "basket"

    return (*_basket_subtotals(basket), "basket")


def _basket_subtotals(basket) -> tuple[Decimal, Decimal]:
    total = Decimal("0.00")
    discountable_total = Decimal("0.00")
    for item in basket.items:
        line_total = item.variant.price * item.quantity
        total += line_total
        if product_is_discountable(item.product):
            discountable_total += line_total
    return quantize_money(total) or Decimal("0.00"), quantize_money(discountable_total) or Decimal("0.00")


def _build_app_referral_option(profile: ReferralProfile, *, user: User, subtotal: Decimal, discountable_subtotal: Decimal) -> ResolvedDiscountOption | None:
    if not user_has_promo_code(user):
        return None

    discount_percent = calculate_personal_discount_percent(profile.referral_discount_base_total, has_promo_code=True)
    if discount_percent <= Decimal("0.00"):
        return None

    estimated_discount_amount = estimate_discount_amount(
        subtotal=discountable_subtotal,
        calculation_mode="percent",
        discount_percent=discount_percent,
        discount_amount=None,
    )
    return ResolvedDiscountOption(
        source_kind="app_referral",
        source_record_id=profile.id,
        code=user.promo_code,
        title="App referral personal discount",
        status="available",
        is_applicable=True,
        is_personal=True,
        is_stackable=False,
        calculation_mode="percent",
        discount_percent=discount_percent,
        discount_amount=None,
        currency="RUB",
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=max(Decimal("0.00"), subtotal - (estimated_discount_amount or Decimal("0.00"))),
        reason=None,
    )


async def _build_bitrix_promo_option(
    code: str | None,
    *,
    subtotal: Decimal,
    discountable_subtotal: Decimal,
    currency: str | None,
) -> tuple[ResolvedDiscountOption | None, str | None]:
    if not code:
        return None, None
    if not bitrix_promo_client.is_configured():
        return None, "Promo code validation is not configured"

    try:
        promo = await bitrix_promo_client.get_promo(code)
    except BitrixPromoIntegrationError as exc:
        logger.warning("Bitrix promo validation failed code=%s error=%s", code, exc)
        return None, "Promo code validation service is unavailable"
    if promo is None:
        return None, "Promo code was not found or is not active"

    estimated_discount_amount = estimate_discount_amount(
        subtotal=discountable_subtotal,
        calculation_mode="percent",
        discount_percent=promo.discount_percent,
        discount_amount=None,
    )
    return ResolvedDiscountOption(
        source_kind="bitrix_promo",
        source_record_id=None,
        code=promo.code,
        title="Bitrix promo code",
        status="available",
        is_applicable=True,
        is_personal=False,
        is_stackable=False,
        calculation_mode="percent",
        discount_percent=promo.discount_percent,
        discount_amount=None,
        currency=currency or "RUB",
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=max(Decimal("0.00"), subtotal - (estimated_discount_amount or Decimal("0.00"))),
        reason=None,
    ), None


def _apply_discount_option(option: ResolvedDiscountOption, *, subtotal: Decimal, discountable_subtotal: Decimal, sequence: int) -> tuple[dict, Decimal]:
    applied_amount = estimate_discount_amount(
        subtotal=discountable_subtotal,
        calculation_mode=option.calculation_mode,
        discount_percent=option.discount_percent,
        discount_amount=option.discount_amount,
    ) or Decimal("0.00")
    applied_amount = min(discountable_subtotal, quantize_money(applied_amount) or Decimal("0.00"))
    next_total = quantize_money(max(Decimal("0.00"), subtotal - applied_amount)) or Decimal("0.00")
    payload = asdict(option)
    payload.update(
        {
            "sequence": sequence,
            "applied_discount_amount": applied_amount,
            "subtotal_before": discountable_subtotal,
            "subtotal_after": next_total,
        }
    )
    return payload, next_total


def _stack_discount_options(*, selected_option: ResolvedDiscountOption | None, subtotal: Decimal, discountable_subtotal: Decimal) -> tuple[list[dict], Decimal, Decimal]:
    if selected_option is None or not selected_option.is_applicable:
        return [], Decimal("0.00"), subtotal

    application, total_after_discount = _apply_discount_option(
        selected_option,
        subtotal=subtotal,
        discountable_subtotal=discountable_subtotal,
        sequence=1,
    )
    discount_total = quantize_money(subtotal - total_after_discount) or Decimal("0.00")
    return [application], discount_total, total_after_discount


async def resolve_benefits_for_user(
    db: AsyncSession,
    *,
    user: User,
    entered_code: str | None = None,
    subtotal: Decimal | None = None,
    discountable_subtotal: Decimal | None = None,
    currency: str | None = None,
) -> dict:
    normalized_code = lower_optional_str(entered_code)
    trimmed_code = optional_str(entered_code)
    effective_subtotal, effective_discountable_subtotal, subtotal_source = await _resolve_subtotals(
        db,
        user_id=user.id,
        explicit_subtotal=subtotal,
        explicit_discountable_subtotal=discountable_subtotal,
    )
    referral_profile = await get_or_create_referral_profile(db, user=user)

    if trimmed_code:
        try:
            referral_profile = await attach_referrer_code(db, user=user, code=trimmed_code, confirmed=True)
        except HTTPException:
            pass

    await refresh_profile_discount_from_moysklad(referral_profile, user=user)
    app_referral_option = _build_app_referral_option(
        referral_profile,
        user=user,
        subtotal=effective_subtotal,
        discountable_subtotal=effective_discountable_subtotal,
    )

    bitrix_promo_option, bitrix_unresolved_reason = await _build_bitrix_promo_option(
        trimmed_code,
        subtotal=effective_subtotal,
        discountable_subtotal=effective_discountable_subtotal,
        currency=currency,
    )

    available_discount_options = [
        option for option in (app_referral_option, bitrix_promo_option) if option is not None and option.is_applicable
    ]
    personal_discount = app_referral_option if app_referral_option is not None and app_referral_option.is_applicable else None
    best_discount = max(available_discount_options, key=best_option_key) if available_discount_options else None
    code_matches = []
    if app_referral_option is not None and normalized_code and lower_optional_str(app_referral_option.code) == normalized_code:
        code_matches.append(app_referral_option)
    if bitrix_promo_option is not None and normalized_code and lower_optional_str(bitrix_promo_option.code) == normalized_code:
        code_matches.append(bitrix_promo_option)

    selected_option = max(code_matches, key=best_option_key) if code_matches else personal_discount

    stacked_discount_options, stacked_discount_amount, total_after_discounts = _stack_discount_options(
        selected_option=selected_option,
        subtotal=effective_subtotal,
        discountable_subtotal=effective_discountable_subtotal,
    )
    resolved_currency = preferred_currency(requested_currency=currency, available_options=available_discount_options)

    unresolved_code_reason = None
    if trimmed_code and not code_matches: unresolved_code_reason = bitrix_unresolved_reason or "Promo code was not found or is not active"

    return {
        "referral_profile_id": referral_profile.id,
        "subtotal_source": subtotal_source,
        "basket_subtotal": effective_subtotal,
        "currency": resolved_currency,
        "entered_code": trimmed_code,
        "entered_code_matches": serialize_options(code_matches),
        "unresolved_code_reason": unresolved_code_reason,
        "available_discount_options": serialize_options(available_discount_options),
        "personal_discount": asdict(personal_discount) if personal_discount is not None else None,
        "best_discount": asdict(best_discount) if best_discount is not None else None,
        "stacked_discount_options": stacked_discount_options,
        "stacked_discount_amount": stacked_discount_amount,
        "total_after_discounts": total_after_discounts,
    }
