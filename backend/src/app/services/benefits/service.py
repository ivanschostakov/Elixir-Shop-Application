from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.app.services.referrals import get_deposit_balance, get_or_create_referral_profile, profile_has_referral_participation
from src.app.services.referrals.calculations import calculate_personal_discount_percent
from src.database.crud import get_basket_by_user_id, get_website_identity_by_user_id
from src.database.models import AppPromo, ReferralProfile, User, WebsiteBonusAccount
from src.normalize import lower_optional_str, optional_str

from .app_promos import build_app_promo_option
from .money import estimate_discount_amount, preferred_currency, quantize_money
from .options import best_option_key, serialize_options
from .types import ResolvedDiscountOption
from .website import build_website_coupon_option, build_website_entitlement_option


async def _resolve_subtotal(db: AsyncSession, *, user_id: int, explicit_subtotal: Decimal | None) -> tuple[Decimal, str]:
    if explicit_subtotal is not None: return quantize_money(explicit_subtotal) or Decimal("0.00"), "request"
    basket = await get_basket_by_user_id(db, user_id)
    if basket is None: return Decimal("0.00"), "basket"
    total = Decimal("0.00")
    for item in basket.items: total += item.variant.price * item.quantity
    return quantize_money(total) or Decimal("0.00"), "basket"


def _resolve_bonus_option(*, bonus_account: WebsiteBonusAccount | None, subtotal: Decimal, requested_bonus_amount: Decimal | None) -> dict | None:
    if bonus_account is None:
        return None

    balance = quantize_money(bonus_account.balance) or Decimal("0.00")
    max_applicable_amount = min(balance, subtotal)
    requested_amount = quantize_money(requested_bonus_amount)
    applicable_amount = max_applicable_amount
    reason: str | None = None
    status = "available"
    is_available = True

    if not bonus_account.is_active:
        status = "inactive"
        is_available = False
        applicable_amount = Decimal("0.00")
        reason = "Website bonus account is not active"
    
    elif max_applicable_amount <= Decimal("0.00"):
        status = "unavailable"
        is_available = False
        applicable_amount = Decimal("0.00")
        reason = "No website bonus balance can be applied to the current subtotal"
    
    elif requested_amount is not None:
        applicable_amount = min(requested_amount, max_applicable_amount)
        if requested_amount > max_applicable_amount: reason = "Requested bonus amount was capped by the available website balance or subtotal"

    return {"status": status, "is_available": is_available, "source_record_id": bonus_account.id, "balance": balance, "currency": bonus_account.currency, "max_applicable_amount": max_applicable_amount, "requested_amount": requested_amount, "applicable_amount": applicable_amount, "estimated_total_after_bonus": quantize_money(max(Decimal("0.00"), subtotal - applicable_amount)) or Decimal("0.00"), "reason": reason, }


def _build_app_referral_option(profile: ReferralProfile, *, subtotal: Decimal) -> ResolvedDiscountOption | None:
    if not profile_has_referral_participation(profile):
        return None

    discount_percent = calculate_personal_discount_percent(profile.referral_discount_base_total, has_referrer=True)
    if discount_percent <= Decimal("0.00"):
        return None

    estimated_discount_amount = estimate_discount_amount(
        subtotal=subtotal,
        calculation_mode="percent",
        discount_percent=discount_percent,
        discount_amount=None,
    )
    return ResolvedDiscountOption(
        source_kind="app_referral",
        source_record_id=profile.id,
        code=profile.referrer_promo_code or "WEBSITE_REFERRAL",
        title="App referral personal discount",
        status="available",
        is_applicable=True,
        is_personal=True,
        is_stackable=True,
        calculation_mode="percent",
        discount_percent=discount_percent,
        discount_amount=None,
        currency="RUB",
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=max(Decimal("0.00"), subtotal - (estimated_discount_amount or Decimal("0.00"))),
        reason=None,
    )


def _apply_discount_option(option: ResolvedDiscountOption, *, running_total: Decimal, sequence: int) -> tuple[dict, Decimal]:
    applied_amount = estimate_discount_amount(
        subtotal=running_total,
        calculation_mode=option.calculation_mode,
        discount_percent=option.discount_percent,
        discount_amount=option.discount_amount,
    ) or Decimal("0.00")
    applied_amount = min(running_total, quantize_money(applied_amount) or Decimal("0.00"))
    next_total = quantize_money(max(Decimal("0.00"), running_total - applied_amount)) or Decimal("0.00")
    payload = asdict(option)
    payload.update(
        {
            "sequence": sequence,
            "applied_discount_amount": applied_amount,
            "subtotal_before": running_total,
            "subtotal_after": next_total,
        }
    )
    return payload, next_total


def _best_applicable(options: list[ResolvedDiscountOption], *, source_kind: str | None = None) -> ResolvedDiscountOption | None:
    candidates = [option for option in options if option.is_applicable and (source_kind is None or option.source_kind == source_kind)]
    candidates.sort(key=best_option_key, reverse=True)
    return candidates[0] if candidates else None


def _stack_discount_options(
    *,
    app_referral_option: ResolvedDiscountOption | None,
    entitlement_options: list[ResolvedDiscountOption],
    code_matches: list[ResolvedDiscountOption],
    subtotal: Decimal,
) -> tuple[list[dict], Decimal, Decimal]:
    ordered_options: list[ResolvedDiscountOption] = []
    if app_referral_option is not None and app_referral_option.is_applicable:
        ordered_options.append(app_referral_option)

    website_personal = _best_applicable(entitlement_options, source_kind="website_discount_entitlement")
    if website_personal is not None:
        ordered_options.append(website_personal)

    website_coupon = _best_applicable(code_matches, source_kind="website_coupon")
    if website_coupon is not None:
        ordered_options.append(website_coupon)

    app_promo = _best_applicable(code_matches, source_kind="app_promo")
    if app_promo is not None:
        ordered_options.append(app_promo)

    running_total = subtotal
    stacked: list[dict] = []
    for sequence, option in enumerate(ordered_options, start=1):
        application, running_total = _apply_discount_option(option, running_total=running_total, sequence=sequence)
        stacked.append(application)

    discount_total = quantize_money(subtotal - running_total) or Decimal("0.00")
    return stacked, discount_total, running_total


def _resolve_deposit_option(
    *,
    balance: Decimal,
    subtotal_after_discounts: Decimal,
    requested_deposit_amount: Decimal | None,
    currency: str | None,
) -> dict:
    requested_amount = quantize_money(requested_deposit_amount)
    max_applicable_amount = min(balance, subtotal_after_discounts)
    applicable_amount = Decimal("0.00")
    status = "not_requested"
    is_available = max_applicable_amount > Decimal("0.00")
    reason = None

    if requested_amount is not None:
        applicable_amount = min(requested_amount, max_applicable_amount)
        status = "available" if applicable_amount > Decimal("0.00") else "unavailable"
        if requested_amount > max_applicable_amount:
            reason = "Requested deposit amount was capped by the available deposit balance or discounted subtotal"
    elif is_available:
        status = "available"

    return {
        "status": status,
        "is_available": is_available,
        "balance": balance,
        "currency": currency or "RUB",
        "max_applicable_amount": max_applicable_amount,
        "requested_amount": requested_amount,
        "applicable_amount": applicable_amount,
        "estimated_total_after_deposit": quantize_money(max(Decimal("0.00"), subtotal_after_discounts - applicable_amount)) or Decimal("0.00"),
        "reason": reason,
    }


async def resolve_benefits_for_user(
    db: AsyncSession,
    *,
    user: User,
    entered_code: str | None = None,
    subtotal: Decimal | None = None,
    currency: str | None = None,
    requested_bonus_amount: Decimal | None = None,
    requested_deposit_amount: Decimal | None = None,
) -> dict:
    normalized_code = lower_optional_str(entered_code)
    trimmed_code = optional_str(entered_code)
    effective_subtotal, subtotal_source = await _resolve_subtotal(db, user_id=user.id, explicit_subtotal=subtotal)
    website_identity = await get_website_identity_by_user_id(db, user.id)
    now = ufa_now()

    coupon_options = []
    entitlement_options = []
    if website_identity is not None:
        coupon_options = [build_website_coupon_option(coupon, subtotal=effective_subtotal) for coupon in website_identity.coupon_snapshots]
        entitlement_options = [build_website_entitlement_option(entitlement, subtotal=effective_subtotal, now=now) for entitlement in website_identity.discount_entitlements]

    code_matches = [option for option in coupon_options if normalized_code and lower_optional_str(option.code) == normalized_code]

    if normalized_code:
        app_promo = (await db.execute(select(AppPromo).where(func.lower(AppPromo.code) == normalized_code))).scalar_one_or_none()
        if app_promo is not None: code_matches.append(await build_app_promo_option(db, app_promo=app_promo, subtotal=effective_subtotal, user_id=user.id, now=now))

    referral_profile = await get_or_create_referral_profile(db, user=user)
    app_referral_option = _build_app_referral_option(referral_profile, subtotal=effective_subtotal)

    available_discount_options = [
        *([app_referral_option] if app_referral_option is not None and app_referral_option.is_applicable else []),
        *[option for option in coupon_options if option.is_applicable],
        *[option for option in entitlement_options if option.is_applicable],
        *[option for option in code_matches if option.source_kind == "app_promo" and option.is_applicable],
    ]
    available_discount_options.sort(key=best_option_key, reverse=True)

    personal_options = [
        *([app_referral_option] if app_referral_option is not None and app_referral_option.is_applicable else []),
        *[option for option in entitlement_options if option.is_applicable],
    ]
    personal_options.sort(key=best_option_key, reverse=True)

    code_matches.sort(key=best_option_key, reverse=True)
    best_discount = available_discount_options[0] if available_discount_options else None
    personal_discount = personal_options[0] if personal_options else None
    bonus_option = _resolve_bonus_option(bonus_account=website_identity.bonus_account_snapshot if website_identity is not None else None, subtotal=effective_subtotal, requested_bonus_amount=requested_bonus_amount, )
    stacked_discount_options, stacked_discount_amount, total_after_discounts = _stack_discount_options(
        app_referral_option=app_referral_option,
        entitlement_options=entitlement_options,
        code_matches=code_matches,
        subtotal=effective_subtotal,
    )
    deposit_balance = await get_deposit_balance(db, user.id)
    resolved_currency = preferred_currency(requested_currency=currency, available_options=available_discount_options, bonus_option=bonus_option)
    deposit_option = _resolve_deposit_option(
        balance=deposit_balance,
        subtotal_after_discounts=total_after_discounts,
        requested_deposit_amount=requested_deposit_amount,
        currency=resolved_currency,
    )

    unresolved_code_reason = None
    if trimmed_code and not code_matches: unresolved_code_reason = "Promo code was not found in website coupons or app promos"

    return {
        "website_identity_id": website_identity.id if website_identity is not None else None,
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
        "bonus_option": bonus_option,
        "deposit_option": deposit_option,
        "total_after_deposit": deposit_option["estimated_total_after_deposit"],
    }
