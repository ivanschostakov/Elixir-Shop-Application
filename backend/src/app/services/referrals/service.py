import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.services.website_identities.payloads import build_bonus_account_payload, build_referral_profile_payload
from src.database.models import (
    BusinessLedgerEntry,
    Order,
    OrderBenefitApplication,
    ReferralCommissionEntry,
    ReferralProfile,
    ReferralPromoCode,
    ReferralRelationship,
    User,
    WebsiteIdentity,
)
from src.normalize import optional_str

from .calculations import (
    MONTHLY_COMMISSION_ACTIVITY_THRESHOLD,
    OWN_PROMO_PURCHASE_THRESHOLD,
    REFERRER_ELIGIBLE_PURCHASE_THRESHOLD,
    calculate_commission_amount,
    calculate_level_one_commission_percent,
    calculate_personal_discount_percent,
    calculate_super_referrer_commission_percent,
    quantize_money,
    quantize_percent,
)

MAX_REFERRAL_TREE_LEVEL = 3
DEPOSIT_ENTRY_TYPES = {"website_bonus_seed", "referral_commission", "manual_adjustment", "deposit_spend"}


def normalize_referral_code(code: str | None) -> str | None:
    normalized = optional_str(code)
    return normalized.upper() if normalized else None


def referral_profile_total_purchases(profile: ReferralProfile) -> Decimal:
    return quantize_money(profile.initial_purchase_balance) + quantize_money(profile.website_seed_purchase_balance) + quantize_money(profile.app_paid_purchase_total)


def _discount_base_from_percent(discount_percent: Decimal | int | float | str | None) -> Decimal:
    percent = quantize_percent(discount_percent)
    if percent >= Decimal("20.00"):
        return Decimal("200000.00")
    if percent >= Decimal("4.00"):
        return quantize_money(percent * Decimal("10000.00"))
    return Decimal("0.00")


def _website_seed_referral_payload(profile: ReferralProfile) -> dict[str, Any]:
    seed_payload = profile.website_seed_payload if isinstance(profile.website_seed_payload, dict) else {}
    referral_payload = seed_payload.get("referral_profile")
    return referral_payload if isinstance(referral_payload, dict) else {}


def _website_seed_referral_percent(profile: ReferralProfile) -> Decimal:
    return quantize_percent(_website_seed_referral_payload(profile).get("referral_percent"))


def profile_has_referral_participation(profile: ReferralProfile) -> bool:
    return bool(profile.referrer_promo_code) or _website_seed_referral_percent(profile) > Decimal("0.00")


def _website_discount_base_from_referral_data(website_referral_data: dict[str, Any] | None) -> Decimal:
    if website_referral_data is None:
        return Decimal("0.00")
    turnover_base = quantize_money(website_referral_data.get("referral_turnover_amount"))
    percent_base = _discount_base_from_percent(website_referral_data.get("referral_percent"))
    return max(turnover_base, percent_base)


def _sync_website_referral_discount_base(
    profile: ReferralProfile,
    *,
    old_website_base: Decimal,
    new_website_base: Decimal,
    is_first_website_seed: bool,
    website_participates: bool,
) -> None:
    participates = website_participates or bool(profile.referrer_promo_code)
    if not participates:
        profile.referral_discount_base_total = Decimal("0.00")
        _refresh_profile_discount(profile)
        return

    current_base = quantize_money(profile.referral_discount_base_total)
    if is_first_website_seed:
        profile.referral_discount_base_total = (
            current_base + new_website_base
            if current_base > Decimal("0.00")
            else quantize_money(profile.initial_purchase_balance) + quantize_money(profile.app_paid_purchase_total) + new_website_base
        )
    else:
        app_side_active_base = max(Decimal("0.00"), current_base - old_website_base)
        profile.referral_discount_base_total = app_side_active_base + new_website_base

    _refresh_profile_discount(profile)


def _period_bounds(period_start: date, period_end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(period_start, time.min, tzinfo=ufa_now().tzinfo)
    end_dt = datetime.combine(period_end, time.min, tzinfo=ufa_now().tzinfo)
    return start_dt, end_dt


async def get_referral_profile_by_user_id(db: AsyncSession, user_id: int) -> ReferralProfile | None:
    return (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user_id))).scalar_one_or_none()


async def get_or_create_referral_profile(db: AsyncSession, *, user: User | None = None, user_id: int | None = None) -> ReferralProfile:
    resolved_user_id = user.id if user is not None else user_id
    if resolved_user_id is None:
        raise ValueError("user or user_id is required")

    profile = await get_referral_profile_by_user_id(db, resolved_user_id)
    if profile is not None:
        return profile

    insert_stmt = (
        insert(ReferralProfile)
        .values(user_id=resolved_user_id, current_discount_percent=Decimal("0.00"))
        .on_conflict_do_nothing(index_elements=[ReferralProfile.user_id])
        .returning(ReferralProfile.id)
    )
    created_profile_id = (await db.execute(insert_stmt)).scalar_one_or_none()

    if created_profile_id is not None:
        profile = await db.get(ReferralProfile, created_profile_id)
    else:
        profile = await get_referral_profile_by_user_id(db, resolved_user_id)

    if profile is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create referral profile")

    return profile


async def _find_referral_promo_code(db: AsyncSession, code: str | None) -> ReferralPromoCode | None:
    normalized = normalize_referral_code(code)
    if normalized is None:
        return None
    return (await db.execute(select(ReferralPromoCode).where(func.lower(ReferralPromoCode.code) == normalized.lower()))).scalar_one_or_none()


async def _active_relationship_for_user(db: AsyncSession, user_id: int) -> ReferralRelationship | None:
    stmt = (
        select(ReferralRelationship)
        .where(ReferralRelationship.referred_user_id == user_id, ReferralRelationship.is_active.is_(True))
        .order_by(ReferralRelationship.started_at.desc(), ReferralRelationship.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _relationship_depth_for_new_referral(db: AsyncSession, referrer_user_id: int) -> int:
    ancestor_count = 0
    current_user_id: int | None = referrer_user_id
    visited: set[int] = set()

    while current_user_id is not None:
        if current_user_id in visited:
            return MAX_REFERRAL_TREE_LEVEL + 1
        visited.add(current_user_id)
        relationship = await _active_relationship_for_user(db, current_user_id)
        if relationship is None or relationship.referrer_user_id is None:
            break
        ancestor_count += 1
        current_user_id = relationship.referrer_user_id

    return ancestor_count + 2


def _refresh_profile_discount(profile: ReferralProfile) -> None:
    profile.current_discount_percent = calculate_personal_discount_percent(
        profile.referral_discount_base_total,
        has_referrer=profile_has_referral_participation(profile),
    )


async def _ensure_referral_promo_code(
    db: AsyncSession,
    *,
    owner_user_id: int,
    code: str,
    source_system: str,
    issued_at: datetime | None = None,
) -> ReferralPromoCode:
    normalized = normalize_referral_code(code)
    if normalized is None:
        raise ValueError("Referral promo code is required")

    existing = await _find_referral_promo_code(db, normalized)
    if existing is not None:
        return existing

    promo = ReferralPromoCode(
        code=normalized,
        owner_user_id=owner_user_id,
        is_active=True,
        source_system=source_system,
        issued_at=issued_at or ufa_now(),
    )
    db.add(promo)
    await db.flush()
    return promo


async def ensure_own_promo_code(db: AsyncSession, profile: ReferralProfile, *, source_system: str = "app") -> ReferralPromoCode | None:
    if profile.own_promo_code:
        return await _ensure_referral_promo_code(
            db,
            owner_user_id=profile.user_id,
            code=profile.own_promo_code,
            source_system=source_system,
            issued_at=profile.own_promo_issued_at,
        )

    if referral_profile_total_purchases(profile) < OWN_PROMO_PURCHASE_THRESHOLD:
        return None

    for _ in range(20):
        candidate = normalize_referral_code(f"EP{profile.user_id}{secrets.token_hex(2)}")
        if candidate and await _find_referral_promo_code(db, candidate) is None:
            profile.own_promo_code = candidate
            profile.own_promo_issued_at = ufa_now()
            return await _ensure_referral_promo_code(db, owner_user_id=profile.user_id, code=candidate, source_system=source_system, issued_at=profile.own_promo_issued_at)

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate referral promo code")


async def _ledger_entry_exists(db: AsyncSession, idempotency_key: str) -> bool:
    stmt = select(BusinessLedgerEntry.id).where(BusinessLedgerEntry.idempotency_key == idempotency_key).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def _create_ledger_entry_if_missing(
    db: AsyncSession,
    *,
    idempotency_key: str,
    user_id: int | None,
    amount: Decimal,
    currency: str,
    entry_type: str,
    direction: str,
    source_system: str,
    source_code: str | None = None,
    order_id: int | None = None,
    order_benefit_application_id: int | None = None,
    referral_commission_entry_id: int | None = None,
    website_identity_id: int | None = None,
    note: str | None = None,
    effective_at: datetime | None = None,
) -> BusinessLedgerEntry | None:
    if await _ledger_entry_exists(db, idempotency_key):
        return None

    entry = BusinessLedgerEntry(
        order_id=order_id,
        order_benefit_application_id=order_benefit_application_id,
        referral_commission_entry_id=referral_commission_entry_id,
        user_id=user_id,
        website_identity_id=website_identity_id,
        entry_type=entry_type,
        direction=direction,
        amount=quantize_money(amount),
        currency=currency,
        source_system=source_system,
        source_code=source_code,
        status="posted",
        effective_at=effective_at or ufa_now(),
        note=note,
        idempotency_key=idempotency_key,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_deposit_balance(db: AsyncSession, user_id: int) -> Decimal:
    rows = list(
        (
            await db.execute(
                select(BusinessLedgerEntry.direction, BusinessLedgerEntry.amount).where(
                    BusinessLedgerEntry.user_id == user_id,
                    BusinessLedgerEntry.status == "posted",
                    BusinessLedgerEntry.entry_type.in_(DEPOSIT_ENTRY_TYPES),
                )
            )
        ).all()
    )
    balance = Decimal("0.00")
    for direction, amount in rows:
        if direction == "credit":
            balance += quantize_money(amount)
        elif direction == "debit":
            balance -= quantize_money(amount)
    return max(Decimal("0.00"), quantize_money(balance))


async def seed_referral_profile_from_website_payload(
    db: AsyncSession,
    *,
    user: User,
    website_identity: WebsiteIdentity,
    payload: dict[str, Any],
) -> ReferralProfile:
    now = website_identity.last_synced_at or ufa_now()
    website_referral_data = build_referral_profile_payload(website_identity_id=website_identity.id, payload=payload, last_synced_at=now)
    website_bonus_data = build_bonus_account_payload(website_identity_id=website_identity.id, payload=payload, last_synced_at=now)
    website_discount_base = _website_discount_base_from_referral_data(website_referral_data)
    website_referral_percent = quantize_percent((website_referral_data or {}).get("referral_percent"))
    website_participates = bool(
        normalize_referral_code((website_referral_data or {}).get("referrer_promo_code"))
        or website_referral_percent > Decimal("0.00")
    )
    profile = await get_or_create_referral_profile(db, user=user)
    is_first_website_seed = profile.website_seeded_at is None
    old_website_discount_base = quantize_money(profile.website_seed_purchase_balance)

    if profile.website_identity_id is None:
        profile.website_identity_id = website_identity.id

    profile.website_seed_payload = jsonable_encoder(
        {
            "website_identity_id": website_identity.id,
            "referral_profile": website_referral_data or {},
            "referral_app_baseline": {
                "participates": website_participates,
                "discount_base_total": website_discount_base,
                "discount_percent": website_referral_percent,
            },
            "bonus_account": website_bonus_data or {},
            "synced_at": now.isoformat(),
        }
    )

    if website_referral_data is not None:
        profile.website_seed_purchase_balance = website_discount_base
        profile.current_month_purchase_total = quantize_money(website_referral_data.get("monthly_paid_orders_amount"))
        if is_first_website_seed:
            profile.website_seeded_at = now

        own_promo_code = normalize_referral_code(website_referral_data.get("own_promo_code"))
        if own_promo_code and not profile.own_promo_code:
            profile.own_promo_code = own_promo_code
            profile.own_promo_issued_at = now
            await _ensure_referral_promo_code(db, owner_user_id=user.id, code=own_promo_code, source_system="website_seed", issued_at=now)

        referrer_promo_code = normalize_referral_code(website_referral_data.get("referrer_promo_code"))
        if referrer_promo_code and not profile.referrer_promo_code:
            promo = await _find_referral_promo_code(db, referrer_promo_code)
            profile.referrer_promo_code = referrer_promo_code
            profile.referrer_user_id = promo.owner_user_id if promo is not None and promo.owner_user_id != user.id else None
            profile.referrer_attached_at = now

        _sync_website_referral_discount_base(
            profile,
            old_website_base=old_website_discount_base,
            new_website_base=website_discount_base,
            is_first_website_seed=is_first_website_seed,
            website_participates=website_participates,
        )

    await ensure_own_promo_code(db, profile, source_system="website_seed")
    _refresh_profile_discount(profile)

    if website_bonus_data is not None:
        bonus_balance = quantize_money(website_bonus_data.get("balance"))
        if bonus_balance > Decimal("0.00"):
            await _create_ledger_entry_if_missing(
                db,
                idempotency_key=f"website_bonus_seed:user:{user.id}",
                user_id=user.id,
                website_identity_id=website_identity.id,
                amount=bonus_balance,
                currency=optional_str(website_bonus_data.get("currency")) or "RUB",
                entry_type="website_bonus_seed",
                direction="credit",
                source_system="website_seed",
                source_code=str(website_identity.website_user_id),
                note="Initial deposit seed from linked website bonus balance",
                effective_at=now,
            )

    await db.flush()
    return profile


async def check_referrer_code(db: AsyncSession, *, user: User, code: str) -> dict[str, Any]:
    normalized_code = normalize_referral_code(code)
    profile = await get_or_create_referral_profile(db, user=user)
    response: dict[str, Any] = {
        "code": normalized_code,
        "is_valid": False,
        "status": "not_found",
        "reason": "Promo code was not found",
        "warning": None,
        "requires_confirmation": False,
        "referrer_user_id": None,
    }
    if normalized_code is None:
        response["status"] = "empty"
        response["reason"] = "Promo code is required"
        return response

    own_code = normalize_referral_code(profile.own_promo_code)
    if own_code and own_code.casefold() == normalized_code.casefold():
        response["status"] = "own_code"
        response["reason"] = "Clients cannot use their own referral promo code"
        return response

    promo = await _find_referral_promo_code(db, normalized_code)
    if promo is None:
        return response

    response["referrer_user_id"] = promo.owner_user_id
    if not promo.is_active:
        response["status"] = "inactive"
        response["reason"] = "Promo code is inactive"
        return response
    if promo.owner_user_id == user.id:
        response["status"] = "own_code"
        response["reason"] = "Clients cannot use their own referral promo code"
        return response

    depth = await _relationship_depth_for_new_referral(db, promo.owner_user_id)
    if depth > MAX_REFERRAL_TREE_LEVEL:
        response["status"] = "max_depth"
        response["reason"] = "Referral tree is already at the maximum supported depth"
        return response

    current_code = normalize_referral_code(profile.referrer_promo_code)
    replacing_website_seed_path = (
        current_code is None
        and _website_seed_referral_percent(profile) > Decimal("0.00")
        and quantize_money(profile.referral_discount_base_total) > Decimal("0.00")
    )
    replacing = bool(current_code and current_code.casefold() != normalized_code.casefold()) or replacing_website_seed_path
    response.update(
        {
            "is_valid": True,
            "status": "available",
            "reason": None,
            "warning": "Changing the referrer promo resets the active referral discount path to 3%" if replacing else None,
            "requires_confirmation": replacing,
            "depth": depth,
        }
    )
    return response


async def attach_referrer_code(db: AsyncSession, *, user: User, code: str, confirmed: bool = False) -> ReferralProfile:
    check = await check_referrer_code(db, user=user, code=code)
    if not check["is_valid"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=check["reason"] or "Invalid promo code")
    if check["requires_confirmation"] and not confirmed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=check["warning"])

    normalized_code = check["code"]
    promo = await _find_referral_promo_code(db, normalized_code)
    if promo is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Promo code was not found")

    profile = await get_or_create_referral_profile(db, user=user)
    now = ufa_now()
    current_code = normalize_referral_code(profile.referrer_promo_code)
    if current_code and current_code.casefold() == normalized_code.casefold():
        return profile

    active_relationships = list(
        (
            await db.execute(
                select(ReferralRelationship).where(
                    ReferralRelationship.referred_user_id == user.id,
                    ReferralRelationship.is_active.is_(True),
                )
            )
        ).scalars().all()
    )
    for relationship in active_relationships:
        relationship.is_active = False
        relationship.ended_at = now

    relationship = ReferralRelationship(
        referred_user_id=user.id,
        referrer_user_id=promo.owner_user_id,
        referral_promo_code_id=promo.id,
        referrer_promo_code=normalized_code,
        depth=int(check.get("depth") or 2),
        source_system="app",
        is_active=True,
        started_at=now,
    )
    db.add(relationship)
    await db.flush()
    for old_relationship in active_relationships:
        old_relationship.replaced_by_relationship_id = relationship.id

    profile.referrer_promo_code = normalized_code
    profile.referrer_user_id = promo.owner_user_id
    profile.referrer_attached_at = profile.referrer_attached_at or now
    profile.promo_changed_at = now if current_code else profile.promo_changed_at
    profile.referral_discount_base_total = Decimal("0.00")
    _refresh_profile_discount(profile)
    await db.flush()
    return profile


async def detach_referrer_code(db: AsyncSession, *, user: User) -> ReferralProfile:
    profile = await get_or_create_referral_profile(db, user=user)
    current_code = normalize_referral_code(profile.referrer_promo_code)
    if current_code is None:
        return profile

    now = ufa_now()
    active_relationships = list(
        (
            await db.execute(
                select(ReferralRelationship).where(
                    ReferralRelationship.referred_user_id == user.id,
                    ReferralRelationship.is_active.is_(True),
                )
            )
        ).scalars().all()
    )
    for relationship in active_relationships:
        relationship.is_active = False
        relationship.ended_at = now

    profile.referrer_promo_code = None
    profile.referrer_user_id = None
    profile.promo_changed_at = now
    profile.referral_discount_base_total = Decimal("0.00")
    _refresh_profile_discount(profile)
    await db.flush()
    return profile


async def _user_paid_order_total_for_period(db: AsyncSession, *, user_id: int, period_start: date, period_end: date) -> Decimal:
    start_dt, end_dt = _period_bounds(period_start, period_end)
    total = (
        await db.execute(
            select(func.coalesce(func.sum(Order.basket_subtotal), 0)).where(
                Order.user_id == user_id,
                Order.is_paid.is_(True),
                Order.is_canceled.is_(False),
                Order.payment_paid_at.is_not(None),
                Order.payment_paid_at >= start_dt,
                Order.payment_paid_at < end_dt,
            )
        )
    ).scalar_one()
    return quantize_money(total)


def _current_previous_month_bounds(now: datetime) -> tuple[date, date, date]:
    current_start = now.date().replace(day=1)
    previous_end = current_start
    previous_month_last_day = current_start - timedelta(days=1)
    previous_start = previous_month_last_day.replace(day=1)
    next_month = (current_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return previous_start, previous_end, next_month


async def finalize_paid_order_referral_effects(db: AsyncSession, order: Order) -> None:
    if not order.is_paid and order.payment_status != "paid":
        return

    effective_at = order.payment_paid_at or ufa_now()
    profile = await get_or_create_referral_profile(db, user_id=order.user_id)
    purchase_key = f"referral_purchase_total:order:{order.id}"
    if not await _ledger_entry_exists(db, purchase_key):
        subtotal = quantize_money(order.basket_subtotal)
        profile.app_paid_purchase_total = quantize_money(profile.app_paid_purchase_total) + subtotal
        if profile_has_referral_participation(profile):
            profile.referral_discount_base_total = quantize_money(profile.referral_discount_base_total) + subtotal

        _refresh_profile_discount(profile)
        await ensure_own_promo_code(db, profile)
        await _create_ledger_entry_if_missing(
            db,
            idempotency_key=purchase_key,
            user_id=order.user_id,
            order_id=order.id,
            amount=subtotal,
            currency=order.currency,
            entry_type="referral_purchase_total",
            direction="credit",
            source_system="app_referral",
            note="Idempotency marker for referral purchase total reconciliation",
            effective_at=effective_at,
        )

    deposit_applications = list(
        (
            await db.execute(
                select(OrderBenefitApplication).where(
                    OrderBenefitApplication.order_id == order.id,
                    OrderBenefitApplication.user_id == order.user_id,
                    OrderBenefitApplication.source_kind == "app_deposit",
                    OrderBenefitApplication.status == "applied",
                )
            )
        ).scalars().all()
    )
    for application in deposit_applications:
        amount = quantize_money(application.bonus_spent_amount)
        if amount <= Decimal("0.00"):
            continue
        await _create_ledger_entry_if_missing(
            db,
            idempotency_key=f"deposit_spend:order:{order.id}:application:{application.id}",
            user_id=order.user_id,
            order_id=order.id,
            order_benefit_application_id=application.id,
            amount=amount,
            currency=application.currency or order.currency,
            entry_type="deposit_spend",
            direction="debit",
            source_system="app_deposit",
            source_code=application.resolved_code,
            note="Deposit spend applied after paid payment reconciliation",
            effective_at=effective_at,
        )

    await db.flush()


async def get_referral_profile_summary(db: AsyncSession, *, user: User) -> dict[str, Any]:
    profile = await get_or_create_referral_profile(db, user=user)
    now = ufa_now()
    current_start = now.date().replace(day=1)
    next_month = (current_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous_start = (current_start - timedelta(days=1)).replace(day=1)

    current_app_total = await _user_paid_order_total_for_period(db, user_id=user.id, period_start=current_start, period_end=next_month)
    previous_app_total = await _user_paid_order_total_for_period(db, user_id=user.id, period_start=previous_start, period_end=current_start)
    website_current = quantize_money(profile.current_month_purchase_total) if profile.website_seeded_at else Decimal("0.00")
    total_purchases = referral_profile_total_purchases(profile)
    _refresh_profile_discount(profile)

    accrued_commissions = quantize_money(
        (
            await db.execute(
                select(func.coalesce(func.sum(ReferralCommissionEntry.commission_amount), 0)).where(
                    ReferralCommissionEntry.referrer_user_id == user.id,
                    ReferralCommissionEntry.status.in_(["posted", "pending"]),
                )
            )
        ).scalar_one()
    )
    deposit_balance = await get_deposit_balance(db, user.id)

    return {
        "user_id": user.id,
        "total_purchases": total_purchases,
        "initial_purchase_balance": quantize_money(profile.initial_purchase_balance),
        "website_seed_purchase_balance": quantize_money(profile.website_seed_purchase_balance),
        "app_paid_purchase_total": quantize_money(profile.app_paid_purchase_total),
        "current_month_purchases": quantize_money(website_current + current_app_total),
        "previous_month_purchases": previous_app_total,
        "current_discount_percent": quantize_percent(profile.current_discount_percent),
        "referrer_promo_code": profile.referrer_promo_code,
        "own_promo_code": profile.own_promo_code,
        "accrued_commissions": accrued_commissions,
        "deposit_balance": deposit_balance,
        "website_seed_metadata": profile.website_seed_payload,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


async def _eligible_for_level_one_commission(db: AsyncSession, *, referrer_user_id: int, period_start: date, period_end: date) -> tuple[bool, ReferralProfile | None, Decimal]:
    profile = await get_referral_profile_by_user_id(db, referrer_user_id)
    if profile is None:
        return False, None, Decimal("0.00")
    period_total = await _user_paid_order_total_for_period(db, user_id=referrer_user_id, period_start=period_start, period_end=period_end)
    eligible = referral_profile_total_purchases(profile) >= REFERRER_ELIGIBLE_PURCHASE_THRESHOLD and period_total >= MONTHLY_COMMISSION_ACTIVITY_THRESHOLD
    return eligible, profile, period_total


async def _eligible_for_super_commission(db: AsyncSession, *, referrer_user_id: int, period_start: date, period_end: date) -> bool:
    period_total = await _user_paid_order_total_for_period(db, user_id=referrer_user_id, period_start=period_start, period_end=period_end)
    return period_total >= MONTHLY_COMMISSION_ACTIVITY_THRESHOLD


async def _create_commission_entry(
    db: AsyncSession,
    *,
    dry_run: bool,
    period_start: date,
    period_end: date,
    order: Order,
    buyer_discount_percent: Decimal,
    referrer_user_id: int,
    referral_relationship_id: int | None,
    level: int,
    promo_code: str | None,
    referrer_discount_percent: Decimal,
    commission_percent: Decimal,
) -> dict[str, Any]:
    amount = calculate_commission_amount(order.basket_subtotal, commission_percent)
    idempotency_key = f"referral_commission:{period_start.isoformat()}:{period_end.isoformat()}:order:{order.id}:user:{referrer_user_id}:level:{level}"
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
        "idempotency_key": idempotency_key,
    }
    if dry_run or (await db.execute(select(ReferralCommissionEntry.id).where(ReferralCommissionEntry.idempotency_key == idempotency_key))).scalar_one_or_none() is not None:
        return payload

    entry = ReferralCommissionEntry(**payload, posted_at=ufa_now())
    db.add(entry)
    await db.flush()
    if amount > Decimal("0.00"):
        await _create_ledger_entry_if_missing(
            db,
            idempotency_key=f"deposit_credit:commission:{entry.id}",
            user_id=referrer_user_id,
            referral_commission_entry_id=entry.id,
            order_id=order.id,
            amount=amount,
            currency=order.currency,
            entry_type="referral_commission",
            direction="credit",
            source_system="app_referral",
            source_code=promo_code,
            note=f"Referral commission level {level}",
            effective_at=ufa_now(),
        )
    return payload


async def run_monthly_commission_calculation(
    db: AsyncSession,
    *,
    period_start: date,
    period_end: date,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    start_dt, end_dt = _period_bounds(period_start, period_end)
    rows = list(
        (
            await db.execute(
                select(Order, OrderBenefitApplication)
                .join(OrderBenefitApplication, OrderBenefitApplication.order_id == Order.id)
                .where(
                    Order.is_paid.is_(True),
                    Order.is_canceled.is_(False),
                    Order.payment_paid_at.is_not(None),
                    Order.payment_paid_at >= start_dt,
                    Order.payment_paid_at < end_dt,
                    OrderBenefitApplication.source_kind == "app_referral",
                    OrderBenefitApplication.status == "applied",
                )
            )
        ).all()
    )
    results: list[dict[str, Any]] = []
    for order, application in rows:
        relationship = None
        if application.referral_relationship_id is not None:
            relationship = (await db.execute(select(ReferralRelationship).where(ReferralRelationship.id == application.referral_relationship_id))).scalar_one_or_none()
        direct_referrer_user_id = relationship.referrer_user_id if relationship is not None else (application.calculation_snapshot or {}).get("referrer_user_id")
        if not direct_referrer_user_id:
            continue

        eligible, referrer_profile, _ = await _eligible_for_level_one_commission(
            db,
            referrer_user_id=int(direct_referrer_user_id),
            period_start=period_start,
            period_end=period_end,
        )
        if eligible and referrer_profile is not None:
            referrer_discount = quantize_percent(referrer_profile.current_discount_percent)
            buyer_discount = quantize_percent(application.discount_percent)
            commission_percent = calculate_level_one_commission_percent(
                referrer_discount_percent=referrer_discount,
                referral_discount_percent=buyer_discount,
                promo_code=application.resolved_code,
            )
            results.append(
                await _create_commission_entry(
                    db,
                    dry_run=dry_run,
                    period_start=period_start,
                    period_end=period_end,
                    order=order,
                    buyer_discount_percent=buyer_discount,
                    referrer_user_id=int(direct_referrer_user_id),
                    referral_relationship_id=relationship.id if relationship is not None else None,
                    level=1,
                    promo_code=application.resolved_code,
                    referrer_discount_percent=referrer_discount,
                    commission_percent=commission_percent,
                )
            )

        if relationship is None or relationship.referrer_user_id is None:
            continue
        super_relationship = await _active_relationship_for_user(db, relationship.referrer_user_id)
        if super_relationship is None or super_relationship.referrer_user_id is None:
            continue
        if not await _eligible_for_super_commission(db, referrer_user_id=super_relationship.referrer_user_id, period_start=period_start, period_end=period_end):
            continue
        results.append(
            await _create_commission_entry(
                db,
                dry_run=dry_run,
                period_start=period_start,
                period_end=period_end,
                order=order,
                buyer_discount_percent=quantize_percent(application.discount_percent),
                referrer_user_id=super_relationship.referrer_user_id,
                referral_relationship_id=super_relationship.id,
                level=3,
                promo_code=super_relationship.referrer_promo_code,
                referrer_discount_percent=Decimal("0.00"),
                commission_percent=calculate_super_referrer_commission_percent(),
            )
        )

    if not dry_run:
        await db.flush()
    return results
