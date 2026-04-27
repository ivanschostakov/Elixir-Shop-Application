from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AppPromo, OrderBenefitApplication
from src.normalize import lower_optional_str

from .money import estimate_discount_amount, quantize_money, total_after
from .types import FIXED_BENEFIT_KINDS, IGNORED_USAGE_STATUSES, PERCENT_BENEFIT_KINDS, ResolvedDiscountOption


def resolve_app_promo_discount(app_promo: AppPromo) -> tuple[str, Decimal | None, Decimal | None, str | None]:
    benefit_kind = lower_optional_str(app_promo.benefit_kind) or ""
    if benefit_kind in PERCENT_BENEFIT_KINDS or (app_promo.discount_percent is not None and app_promo.discount_amount is None): return "percent", quantize_money(app_promo.discount_percent), None, None
    if benefit_kind in FIXED_BENEFIT_KINDS or app_promo.discount_amount is not None: return "fixed_amount", None, quantize_money(app_promo.discount_amount), None
    return "unknown", None, None, "App promo exists, but its benefit type is not supported yet"


async def app_promo_usage_counts(db: AsyncSession, *, app_promo_id: int, user_id: int) -> tuple[int, int]:
    base_filters = (
        OrderBenefitApplication.app_promo_id == app_promo_id,
        ~func.lower(OrderBenefitApplication.status).in_(IGNORED_USAGE_STATUSES),
    )
    total_stmt = select(func.count(OrderBenefitApplication.id)).where(*base_filters)
    user_stmt = select(func.count(OrderBenefitApplication.id)).where(*base_filters, OrderBenefitApplication.user_id == user_id)
    total_uses = int((await db.execute(total_stmt)).scalar_one() or 0)
    user_uses = int((await db.execute(user_stmt)).scalar_one() or 0)
    return total_uses, user_uses


async def build_app_promo_option(
    db: AsyncSession, *, app_promo: AppPromo, subtotal: Decimal, user_id: int, now: Any
) -> ResolvedDiscountOption:
    calculation_mode, discount_percent, discount_amount, reason = resolve_app_promo_discount(app_promo)
    status = "available"
    is_applicable = True

    if calculation_mode == "unknown":
        status = "unsupported"
        is_applicable = False

    elif not app_promo.is_active:
        status = "inactive"
        is_applicable = False
        reason = "App promo is disabled"

    elif app_promo.starts_at and app_promo.starts_at > now:
        status = "scheduled"
        is_applicable = False
        reason = "App promo is not active yet"

    elif app_promo.ends_at and app_promo.ends_at < now:
        status = "expired"
        is_applicable = False
        reason = "App promo has expired"

    else:
        total_uses, user_uses = await app_promo_usage_counts(db, app_promo_id=app_promo.id, user_id=user_id)
        if app_promo.max_total_uses is not None and total_uses >= app_promo.max_total_uses:
            status = "usage_limit_reached"
            is_applicable = False
            reason = "App promo total usage limit has been reached"

        elif app_promo.max_uses_per_user is not None and user_uses >= app_promo.max_uses_per_user:
            status = "usage_limit_reached"
            is_applicable = False
            reason = "App promo usage limit has been reached for this user"

    estimated_discount_amount = None
    if is_applicable: estimated_discount_amount = estimate_discount_amount(subtotal=subtotal, calculation_mode=calculation_mode, discount_percent=discount_percent, discount_amount=discount_amount)

    return ResolvedDiscountOption(
        source_kind="app_promo",
        source_record_id=app_promo.id,
        code=app_promo.code,
        title=app_promo.name,
        status=status,
        is_applicable=is_applicable,
        is_personal=False,
        is_stackable=(lower_optional_str(app_promo.stacking_policy) or "") != "exclusive",
        calculation_mode=calculation_mode,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        currency=app_promo.currency,
        estimated_discount_amount=estimated_discount_amount,
        estimated_total_after=total_after(subtotal, estimated_discount_amount),
        reason=reason,
    )
