from dataclasses import asdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import LOYALTY_BONUS_LIFETIME_DAYS, LOYALTY_ORDER_CASHBACK_PERCENT
from src.app.services.discounts import product_is_discountable
from src.app.services.catalog_merchandising import catalog_unit_price
from src.app.services.referrals import (
    ensure_default_reward_program,
    normalize_reward_program,
    refresh_profile_discount,
    reward_program_selection_required,
)
from src.app.services.referrals.bitrix_sync import refresh_program_profile_from_bitrix
from src.app.services.referrals.calculations import MIN_PARTICIPANT_DISCOUNT_PERCENT
from src.database.crud import get_basket_by_user_id
from src.database.models import ReferralProfile, User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import lower_optional_str, optional_str

from .money import estimate_discount_amount, preferred_currency, quantize_money
from .moysklad_bonus import bonus_spend_for_subtotal, get_user_moysklad_bonus_wallet
from .loyalty import (
    REWARD_MODE_CASHBACK,
    REWARD_MODE_PROMO,
    cashback_points_for_amount,
    pending_loyalty_bonus_points,
)
from .options import best_option_key, serialize_options
from .types import ResolvedDiscountOption


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
        line_total = catalog_unit_price(item.variant.price, item.product) * item.quantity
        total += line_total
        if product_is_discountable(item.product):
            discountable_total += line_total
    return quantize_money(total) or Decimal("0.00"), quantize_money(discountable_total) or Decimal("0.00")


def _build_app_referral_option(profile: ReferralProfile, *, user: User, subtotal: Decimal, discountable_subtotal: Decimal) -> ResolvedDiscountOption | None:
    attached_promo = optional_str(user.promo_code)
    if not attached_promo:
        return None
    discount_percent = profile.current_discount_percent
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
        code=attached_promo,
        title="Персональная скидка / Personal discount",
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


def _basket_quote_items(basket) -> list[dict]:
    if basket is None:
        return []
    return [
        {
            "variant_system_id": str(item.variant.system_id),
            "product_system_id": str(item.product.system_id),
            "sku": item.variant.sku or item.product.sku,
            "quantity": item.quantity,
        }
        for item in basket.items
        if item.variant is not None and item.product is not None
    ]


def _build_bitrix_promo_option(
    *,
    code: str,
    lookup: dict,
    quote: dict | None,
    subtotal: Decimal,
    discountable_subtotal: Decimal,
    fixed_discount_percent: Decimal | None = None,
) -> ResolvedDiscountOption:
    discount_percent = quantize_money(
        quote.get("effective_discount_percent")
        if quote is not None and quote.get("effective_discount_percent") is not None
        else lookup.get("discount_percent")
    )
    discount_amount = quantize_money(quote.get("discount_amount")) if quote is not None else None
    is_applicable = bool(quote and quote.get("is_applicable") and discount_amount and discount_amount > 0)
    calculation_mode = "fixed_amount"
    estimated_total_after = (
        quantize_money(quote.get("final_total"))
        if quote is not None
        else None
    )
    if fixed_discount_percent is not None:
        discount_percent = fixed_discount_percent
        calculation_mode = "percent"
        discount_amount = None
        estimated_discount_amount = estimate_discount_amount(
            subtotal=discountable_subtotal,
            calculation_mode="percent",
            discount_percent=fixed_discount_percent,
            discount_amount=None,
        ) if is_applicable else None
        estimated_total_after = (
            max(Decimal("0.00"), subtotal - estimated_discount_amount)
            if estimated_discount_amount is not None
            else None
        )
    else:
        estimated_discount_amount = discount_amount
    status = "available" if is_applicable else ("requires_cart" if quote is None else "not_applicable")
    reason = None
    if quote is None:
        reason = "Добавьте товары в корзину для расчёта / Add products to the cart for calculation"
    elif not is_applicable:
        reason = "Промокод не применяется к этой корзине / Promo code does not apply to this cart"

    return ResolvedDiscountOption(
        source_kind="bitrix_promo",
        source_record_id=int(lookup["discount_id"]) if lookup.get("discount_id") else None,
        code=str(lookup.get("promo") or code),
        title=str(lookup.get("discount_name") or "Промокод Bitrix / Bitrix promo"),
        status=status,
        is_applicable=is_applicable,
        is_personal=True,
        is_stackable=False,
        calculation_mode=calculation_mode,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        currency=str(quote.get("currency")) if quote and quote.get("currency") else None,
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=estimated_total_after,
        reason=reason,
    )


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
    quote_items: list[dict] | None = None,
    use_bonus_rubles: bool = False,
    reward_mode: str | None = None,
) -> dict:
    normalized_code = lower_optional_str(entered_code)
    trimmed_code = optional_str(entered_code)
    effective_subtotal, effective_discountable_subtotal, subtotal_source = await _resolve_subtotals(
        db,
        user_id=user.id,
        explicit_subtotal=subtotal,
        explicit_discountable_subtotal=discountable_subtotal,
    )
    referral_profile = await ensure_default_reward_program(db, user=user)
    reward_program = normalize_reward_program(referral_profile.reward_program) or "bonus"
    if optional_str(user.promo_code) or reward_program == "partner":
        remote_program_profile = await refresh_program_profile_from_bitrix(
            db,
            user=user,
        )
        if remote_program_profile is None:
            refresh_profile_discount(
                referral_profile,
                has_promo_code=bool(optional_str(user.promo_code)),
            )
    else:
        refresh_profile_discount(
            referral_profile,
            has_promo_code=bool(optional_str(user.promo_code)),
        )
    bonus_wallet = await get_user_moysklad_bonus_wallet(user)
    # reward_mode is accepted for compatibility with already installed app
    # builds. Promo availability and the selected program are authoritative.
    del reward_mode
    effective_code = trimmed_code or optional_str(user.promo_code)
    resolved_reward_mode = REWARD_MODE_PROMO if effective_code else REWARD_MODE_CASHBACK
    bitrix_option = None
    app_referral_option = (
        _build_app_referral_option(
            referral_profile,
            user=user,
            subtotal=effective_subtotal,
            discountable_subtotal=effective_discountable_subtotal,
        )
        if effective_code
        else None
    )
    if bitrix_promo_configured() and effective_code:
        client = BitrixPromoClient()
        try:
            lookup = await client.lookup(effective_code)
            resolved_quote_items = quote_items
            if resolved_quote_items is None:
                resolved_quote_items = _basket_quote_items(await get_basket_by_user_id(db, user.id))
            quote = (
                await client.quote(
                    promo=effective_code,
                    items=resolved_quote_items,
                    user_email=user.email,
                )
                if resolved_quote_items
                else None
            )
            attached_code = lower_optional_str(user.promo_code)
            is_assigned_referral_code = bool(
                attached_code
                and attached_code == lower_optional_str(effective_code)
            )
            is_referral_code = bool(
                quote
                and quote.get("is_referral_promo")
            )
            bitrix_option = _build_bitrix_promo_option(
                code=effective_code,
                lookup=lookup,
                quote=quote,
                subtotal=effective_subtotal,
                discountable_subtotal=effective_discountable_subtotal,
                fixed_discount_percent=(
                    MIN_PARTICIPANT_DISCOUNT_PERCENT
                    if reward_program == "bonus"
                    and (is_assigned_referral_code or is_referral_code)
                    else None
                ),
            )
        except BitrixPromoError as error:
            if error.status_code >= 500:
                raise HTTPException(
                    status_code=503,
                    detail="Расчёт промокода временно недоступен / Promo calculation is temporarily unavailable",
                ) from error

    personal_discount_candidates = [
        option
        for option in (bitrix_option, app_referral_option)
        if option is not None and option.is_applicable
    ]
    personal_discount = (
        max(personal_discount_candidates, key=best_option_key)
        if personal_discount_candidates
        else None
    )
    available_discount_options = (
        [personal_discount] if personal_discount is not None and personal_discount.is_applicable else []
    )
    best_discount = max(available_discount_options, key=best_option_key) if available_discount_options else None
    code_matches = []
    for option in (bitrix_option, app_referral_option):
        if option is not None and normalized_code and lower_optional_str(option.code) == normalized_code:
            code_matches.append(option)

    applicable_code_matches = [option for option in code_matches if option.is_applicable]
    selected_option = max(applicable_code_matches, key=best_option_key) if applicable_code_matches else personal_discount
    stacked_discount_options, stacked_discount_amount, total_after_discounts = _stack_discount_options(
        selected_option=selected_option,
        subtotal=effective_subtotal,
        discountable_subtotal=effective_discountable_subtotal,
    )
    bonus_points, bonus_rubles = bonus_spend_for_subtotal(
        bonus_wallet,
        total_after_discounts,
    )
    bonus_option = (
        ResolvedDiscountOption(
            source_kind="moysklad_bonus",
            source_record_id=None,
            source_external_id=str(bonus_wallet.program_id) if bonus_wallet.program_id else None,
            code=None,
            title="Бонусные рубли",
            status="available" if bonus_points > 0 else "not_applicable",
            is_applicable=bonus_points > 0,
            is_personal=True,
            is_stackable=True,
            calculation_mode="fixed_amount",
            discount_percent=None,
            discount_amount=bonus_rubles,
            currency="RUB",
            estimated_discount_amount=bonus_rubles,
            estimated_total_after=quantize_money(total_after_discounts - bonus_rubles),
            reason=None if bonus_points > 0 else "Бонусные рубли недоступны для этой корзины",
            benefit_units=Decimal(bonus_points),
            benefit_unit_name="points",
        )
        if bonus_wallet.program_id is not None
        else None
    )
    if use_bonus_rubles and bonus_option is not None and bonus_option.is_applicable:
        bonus_application, total_after_discounts = _apply_discount_option(
            bonus_option,
            subtotal=total_after_discounts,
            discountable_subtotal=total_after_discounts,
            sequence=len(stacked_discount_options) + 1,
        )
        stacked_discount_options.append(bonus_application)
        stacked_discount_amount = (
            quantize_money(stacked_discount_amount + bonus_rubles) or Decimal("0.00")
        )
    cashback_earned_points = (
        cashback_points_for_amount(total_after_discounts)
        if reward_program == "bonus"
        else 0
    )
    pending_bonus_points = await pending_loyalty_bonus_points(db, user_id=user.id)
    pending_bonus_rubles = (
        quantize_money(
            Decimal(pending_bonus_points) / Decimal(max(1, bonus_wallet.spend_rate_points_to_ruble))
        )
        or Decimal("0.00")
    )
    resolved_currency = preferred_currency(requested_currency=currency, available_options=available_discount_options)

    unresolved_code_reason = None
    if trimmed_code and not code_matches:
        unresolved_code_reason = "Промокод не найден или неактивен / Promo code was not found or is not active"
    elif trimmed_code and code_matches and not applicable_code_matches:
        unresolved_code_reason = code_matches[0].reason

    return {
        "referral_profile_id": referral_profile.id,
        "reward_program": reward_program,
        "program_selection_required": reward_program_selection_required(referral_profile),
        "reward_mode": resolved_reward_mode,
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
        "bonus_option": asdict(bonus_option) if bonus_option is not None else None,
        "bonus_balance_points": bonus_wallet.balance_points + pending_bonus_points,
        "bonus_balance_rubles": bonus_wallet.balance_rubles + pending_bonus_rubles,
        "bonus_pending_points": pending_bonus_points,
        "bonus_pending_rubles": pending_bonus_rubles,
        "bonus_program_name": bonus_wallet.program_name,
        "bonus_max_paid_rate_percent": bonus_wallet.max_paid_rate_percent,
        "use_bonus_rubles": use_bonus_rubles,
        "bonus_applied_points": bonus_points if use_bonus_rubles else 0,
        "bonus_applied_rubles": bonus_rubles if use_bonus_rubles else Decimal("0.00"),
        "cashback_percent": Decimal(str(max(0, min(100, int(LOYALTY_ORDER_CASHBACK_PERCENT))))),
        "cashback_earned_points": cashback_earned_points,
        "cashback_expires_in_days": max(1, int(LOYALTY_BONUS_LIFETIME_DAYS)),
    }
