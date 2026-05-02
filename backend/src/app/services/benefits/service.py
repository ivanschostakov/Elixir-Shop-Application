from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.crud import get_basket_by_user_id, get_website_identity_by_user_id
from src.database.models import AppPromo, User, WebsiteBonusAccount
from src.normalize import lower_optional_str, optional_str

from .app_promos import build_app_promo_option
from .money import preferred_currency, quantize_money
from .options import best_option_key, serialize_options
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


async def resolve_benefits_for_user(db: AsyncSession, *, user: User, entered_code: str | None = None, subtotal: Decimal | None = None, currency: str | None = None, requested_bonus_amount: Decimal | None = None) -> dict:
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

    available_discount_options = [*[option for option in coupon_options if option.is_applicable], *[option for option in entitlement_options if option.is_applicable], *[option for option in code_matches if option.source_kind == "app_promo" and option.is_applicable], ]
    available_discount_options.sort(key=best_option_key, reverse=True)

    personal_options = [option for option in entitlement_options if option.is_applicable]
    personal_options.sort(key=best_option_key, reverse=True)

    code_matches.sort(key=best_option_key, reverse=True)
    best_discount = available_discount_options[0] if available_discount_options else None
    personal_discount = personal_options[0] if personal_options else None
    bonus_option = _resolve_bonus_option(bonus_account=website_identity.bonus_account_snapshot if website_identity is not None else None, subtotal=effective_subtotal, requested_bonus_amount=requested_bonus_amount, )

    unresolved_code_reason = None
    if trimmed_code and not code_matches: unresolved_code_reason = "Promo code was not found in website coupons or app promos"

    return {"website_identity_id": website_identity.id if website_identity is not None else None, "subtotal_source": subtotal_source, "basket_subtotal": effective_subtotal, "currency": preferred_currency(requested_currency=currency, available_options=available_discount_options, bonus_option=bonus_option), "entered_code": trimmed_code, "entered_code_matches": serialize_options(code_matches), "unresolved_code_reason": unresolved_code_reason, "available_discount_options": serialize_options(available_discount_options), "personal_discount": asdict(personal_discount) if personal_discount is not None else None, "best_discount": asdict(best_discount) if best_discount is not None else None, "bonus_option": bonus_option, }
