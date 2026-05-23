from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import Order, OrderBenefitApplication, ReferralCommissionEntry, ReferralRelationship
from .calculations import MONTHLY_COMMISSION_ACTIVITY_THRESHOLD, REFERRER_ELIGIBLE_PURCHASE_THRESHOLD, calculate_commission_amount, calculate_level_one_commission_percent, calculate_super_referrer_commission_percent, quantize_money, quantize_percent
from .ledger import create_ledger_entry_if_missing, ledger_entry_exists
from .profile import get_or_create_referral_profile, get_referral_profile_by_user_id, profile_has_referral_participation, referral_profile_total_purchases, refresh_profile_discount
from .promo import active_relationship_for_user, ensure_own_promo_code


def period_bounds(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    return datetime.combine(period_start, time.min, tzinfo=ufa_now().tzinfo), datetime.combine(period_end, time.min, tzinfo=ufa_now().tzinfo)


async def user_paid_order_total_for_period(db: AsyncSession, *, user_id: int, period_start: date, period_end: date) -> Decimal:
    start, end = period_bounds(period_start, period_end)
    total = (await db.execute(select(func.coalesce(func.sum(Order.basket_subtotal), 0)).where(Order.user_id == user_id, Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.payment_paid_at.is_not(None), Order.payment_paid_at >= start, Order.payment_paid_at < end))).scalar_one()
    return quantize_money(total)


def current_previous_month_bounds(now: datetime) -> tuple[date, date, date]:
    current_start = now.date().replace(day=1)
    previous_end = current_start
    previous_start = (current_start - timedelta(days=1)).replace(day=1)
    next_month = (current_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return previous_start, previous_end, next_month


async def finalize_paid_order_referral_effects(db: AsyncSession, order: Order) -> None:
    if not order.is_paid and order.payment_status != "paid": return

    profile = await get_or_create_referral_profile(db, user_id=order.user_id)
    effective_at, key = order.payment_paid_at or ufa_now(), f"referral_purchase_total:order:{order.id}"

    if not await ledger_entry_exists(db, key):
        subtotal = quantize_money(order.basket_subtotal)
        profile.app_paid_purchase_total = quantize_money(profile.app_paid_purchase_total) + subtotal
        if profile_has_referral_participation(profile): profile.referral_discount_base_total = quantize_money(profile.referral_discount_base_total) + subtotal

        refresh_profile_discount(profile)
        await ensure_own_promo_code(db, profile)
        await create_ledger_entry_if_missing(db, idempotency_key=key, user_id=order.user_id, order_id=order.id, amount=subtotal, currency=order.currency, entry_type="referral_purchase_total", direction="credit", source_system="app_referral", note="Idempotency marker for referral purchase total reconciliation", effective_at=effective_at)

    applications = list((await db.execute(select(OrderBenefitApplication).where(OrderBenefitApplication.order_id == order.id, OrderBenefitApplication.user_id == order.user_id, OrderBenefitApplication.source_kind == "app_deposit", OrderBenefitApplication.status == "applied"))).scalars())
    for app in applications:
        amount = quantize_money(app.bonus_spent_amount)
        if amount <= Decimal("0.00"): continue
        await create_ledger_entry_if_missing(db, idempotency_key=f"deposit_spend:order:{order.id}:application:{app.id}", user_id=order.user_id, order_id=order.id, order_benefit_application_id=app.id, amount=amount, currency=app.currency or order.currency, entry_type="deposit_spend", direction="debit", source_system="app_deposit", source_code=app.resolved_code, note="Deposit spend applied after paid payment reconciliation", effective_at=effective_at)

    await db.flush()


async def eligible_for_level_one_commission(db: AsyncSession, *, referrer_user_id: int, period_start: date, period_end: date):
    profile = await get_referral_profile_by_user_id(db, referrer_user_id)
    if profile is None: return False, None, Decimal("0.00")

    total = await user_paid_order_total_for_period(db, user_id=referrer_user_id, period_start=period_start, period_end=period_end)
    eligible = referral_profile_total_purchases(profile) >= REFERRER_ELIGIBLE_PURCHASE_THRESHOLD and total >= MONTHLY_COMMISSION_ACTIVITY_THRESHOLD
    return eligible, profile, total


async def eligible_for_super_commission(db: AsyncSession, *, referrer_user_id: int, period_start: date, period_end: date) -> bool:
    return await user_paid_order_total_for_period(db, user_id=referrer_user_id, period_start=period_start, period_end=period_end) >= MONTHLY_COMMISSION_ACTIVITY_THRESHOLD


async def create_commission_entry(db: AsyncSession, *, dry_run: bool, period_start: date, period_end: date, order: Order, buyer_discount_percent: Decimal, referrer_user_id: int, referral_relationship_id: int | None, level: int, promo_code: str | None, referrer_discount_percent: Decimal, commission_percent: Decimal) -> dict[str, Any]:
    amount = calculate_commission_amount(order.basket_subtotal, commission_percent)
    key = f"referral_commission:{period_start.isoformat()}:{period_end.isoformat()}:order:{order.id}:user:{referrer_user_id}:level:{level}"
    payload = {
        "period_start": period_start,
        "period_end": period_end,
        "order_id": order.id,
        "buyer_user_id": order.user_id,
        "referrer_user_id": referrer_user_id,
        "referral_relationship_id": referral_relationship_id,
        "level": level,
        "promo_code": promo_code,
        "buyer_discount_percent": buyer_discount_percent,
        "referrer_discount_percent": referrer_discount_percent,
        "commission_percent": commission_percent,
        "order_subtotal": quantize_money(order.basket_subtotal),
        "commission_amount": amount,
        "currency": order.currency,
        "status": "dry_run" if dry_run else "posted",
        "idempotency_key": key,
    }

    exists = (await db.execute(select(ReferralCommissionEntry.id).where(ReferralCommissionEntry.idempotency_key == key))).scalar_one_or_none() is not None
    if dry_run or exists:
        return payload

    entry = ReferralCommissionEntry(**payload, posted_at=ufa_now())
    db.add(entry)
    await db.flush()

    if amount > Decimal("0.00"):
        await create_ledger_entry_if_missing(db, idempotency_key=f"deposit_credit:commission:{entry.id}", user_id=referrer_user_id, referral_commission_entry_id=entry.id, order_id=order.id, amount=amount, currency=order.currency, entry_type="referral_commission", direction="credit", source_system="app_referral", source_code=promo_code, note=f"Referral commission level {level}", effective_at=ufa_now())

    return payload


async def run_monthly_commission_calculation(db: AsyncSession, *, period_start: date, period_end: date, dry_run: bool = False) -> list[dict[str, Any]]:
    start, end = period_bounds(period_start, period_end)
    rows = list((await db.execute(select(Order, OrderBenefitApplication).join(OrderBenefitApplication, OrderBenefitApplication.order_id == Order.id).where(Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.payment_paid_at.is_not(None), Order.payment_paid_at >= start, Order.payment_paid_at < end, OrderBenefitApplication.source_kind == "app_referral", OrderBenefitApplication.status == "applied"))).all())
    results: list[dict[str, Any]] = []

    for order, app in rows:
        relationship = (await db.execute(select(ReferralRelationship).where(ReferralRelationship.id == app.referral_relationship_id))).scalar_one_or_none() if app.referral_relationship_id else None
        referrer_id = relationship.referrer_user_id if relationship else (app.calculation_snapshot or {}).get("referrer_user_id")
        if not referrer_id:
            continue

        eligible, profile, _ = await eligible_for_level_one_commission(db, referrer_user_id=int(referrer_id), period_start=period_start, period_end=period_end)
        if eligible and profile:
            referrer_discount = quantize_percent(profile.current_discount_percent)
            buyer_discount = quantize_percent(app.discount_percent)
            commission_percent = calculate_level_one_commission_percent(
                referrer_discount_percent=referrer_discount,
                referral_discount_percent=buyer_discount,
                promo_code=app.resolved_code,
            )
            results.append(
                await create_commission_entry(
                    db,
                    dry_run=dry_run,
                    period_start=period_start,
                    period_end=period_end,
                    order=order,
                    buyer_discount_percent=buyer_discount,
                    referrer_user_id=int(referrer_id),
                    referral_relationship_id=relationship.id if relationship else None,
                    level=1,
                    promo_code=app.resolved_code,
                    referrer_discount_percent=referrer_discount,
                    commission_percent=commission_percent,
                )
            )

        if relationship is None or relationship.referrer_user_id is None:
            continue
        super_relationship = await active_relationship_for_user(db, relationship.referrer_user_id)
        if super_relationship is None or super_relationship.referrer_user_id is None:
            continue
        if not await eligible_for_super_commission(db, referrer_user_id=super_relationship.referrer_user_id, period_start=period_start, period_end=period_end):
            continue

        results.append(
            await create_commission_entry(
                db,
                dry_run=dry_run,
                period_start=period_start,
                period_end=period_end,
                order=order,
                buyer_discount_percent=quantize_percent(app.discount_percent),
                referrer_user_id=super_relationship.referrer_user_id,
                referral_relationship_id=super_relationship.id,
                level=3,
                promo_code=super_relationship.referrer_promo_code,
                referrer_discount_percent=Decimal("0.00"),
                commission_percent=calculate_super_referrer_commission_percent(),
            )
        )

    if not dry_run: await db.flush()
    return results
