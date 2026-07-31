import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import (
    AppReferralAccrual,
    AppReferralPurchase,
    BonusProgramPurchase,
    Order,
    ReferralProfile,
    User,
)
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import optional_str

from .bitrix_sync import refresh_program_profile_from_bitrix
from .calculations import PARTNER_UNLOCK_SPEND, quantize_money
from .profile import refresh_profile_discount
from .program import ensure_unified_reward_program

logger = logging.getLogger(__name__)


def _paid_order_promo(order: Order) -> str | None:
    checkout_snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = checkout_snapshot.get("benefits")
    benefits = benefits if isinstance(benefits, dict) else {}
    applications = benefits.get("applications")
    if not isinstance(applications, list):
        return None

    for application in applications:
        if not isinstance(application, dict):
            continue
        if code := optional_str(application.get("code")):
            return code
    return None


def _period_bounds(paid_at: datetime) -> tuple[date, date]:
    period_start = date(paid_at.year, paid_at.month, 1)
    if paid_at.month == 12:
        return period_start, date(paid_at.year + 1, 1, 1)
    return period_start, date(paid_at.year, paid_at.month + 1, 1)


def _rewardable_order_amount(order: Order) -> Decimal:
    checkout_snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = checkout_snapshot.get("benefits")
    benefits = benefits if isinstance(benefits, dict) else {}
    total_after_discounts = benefits.get("total_after_discounts")
    if total_after_discounts is not None:
        try:
            return max(Decimal("0.00"), Decimal(str(total_after_discounts)))
        except Exception:
            logger.warning(
                "Could not parse merchandise total from checkout snapshot order_id=%s",
                order.id,
            )

    return max(
        Decimal("0.00"),
        Decimal(str(order.grand_total)) - Decimal(str(order.delivery_total)),
    )


def _purchase_participates_in_program(purchase: AppReferralPurchase) -> bool:
    snapshot = (
        purchase.calculation_snapshot
        if isinstance(purchase.calculation_snapshot, dict)
        else {}
    )
    explicit = snapshot.get("participates_in_program")
    if explicit is not None:
        return bool(explicit)
    return bool(optional_str(purchase.promo_code))


async def _purchase_for_order(
    db: AsyncSession,
    order_id: int,
) -> AppReferralPurchase | None:
    return (
        await db.execute(
            select(AppReferralPurchase)
            .options(selectinload(AppReferralPurchase.accruals))
            .where(AppReferralPurchase.order_id == order_id)
        )
    ).scalar_one_or_none()


async def _local_user_id_for_email(db: AsyncSession, email: str | None) -> int | None:
    normalized = optional_str(email)
    if not normalized:
        return None
    return (
        await db.execute(
            select(User.id)
            .where(func.lower(User.email) == normalized.casefold())
            .limit(1)
        )
    ).scalar_one_or_none()


def _local_calculation(
    *,
    order: Order,
    promo: str | None,
    amount: Decimal,
    paid_at: datetime,
    participates_in_program: bool,
) -> dict[str, Any]:
    return {
        "storage": "app",
        "bitrix_writes": False,
        "program": "combined",
        "promo": promo,
        "promo_mode": "unresolved" if promo else "none",
        "participates_in_program": participates_in_program,
        "amount": str(amount),
        "currency": order.currency,
        "paid_at": paid_at.isoformat(),
        "accruals": [],
    }


async def _increment_local_purchase_progress(
    db: AsyncSession,
    *,
    user: User,
    order_id: int,
    amount: Decimal,
    participates_in_program: bool,
) -> None:
    if not participates_in_program:
        return
    legacy_purchase = (
        await db.execute(
            select(BonusProgramPurchase.id).where(
                BonusProgramPurchase.order_id == order_id,
                BonusProgramPurchase.status == "posted",
            )
        )
    ).scalar_one_or_none()
    if legacy_purchase is not None:
        return

    await ensure_unified_reward_program(db, user=user)
    profile = (
        await db.execute(
            select(ReferralProfile)
            .where(ReferralProfile.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    profile.referral_discount_base_total = quantize_money(
        profile.referral_discount_base_total + amount
    )
    refresh_profile_discount(profile, has_promo_code=True)
    if profile.referral_discount_base_total >= PARTNER_UNLOCK_SPEND:
        profile.partner_unlocked_at = (
            profile.partner_unlocked_at or datetime.now(timezone.utc)
        )


async def _apply_remote_purchase_progress(
    db: AsyncSession,
    *,
    purchase: AppReferralPurchase,
    progress: dict[str, Any] | None,
) -> None:
    if not isinstance(progress, dict) or purchase.buyer_user_id is None:
        return
    try:
        purchase_total = quantize_money(progress.get("new_total"))
        discount_percent = Decimal(str(progress.get("discount_percent") or 0))
    except (ArithmeticError, TypeError, ValueError):
        logger.warning(
            "Could not parse Bitrix purchase progress purchase_id=%s",
            purchase.id,
        )
        return

    profile = (
        await db.execute(
            select(ReferralProfile)
            .where(ReferralProfile.user_id == purchase.buyer_user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if profile is None:
        return
    profile.referral_discount_base_total = purchase_total
    profile.current_discount_percent = discount_percent
    profile.bitrix_sync_status = "synced"
    profile.bitrix_synced_at = datetime.now(timezone.utc)
    profile.bitrix_sync_error = None
    if purchase.bitrix_buyer_user_id:
        profile.bitrix_user_id = purchase.bitrix_buyer_user_id
    if purchase_total >= PARTNER_UNLOCK_SPEND:
        profile.partner_unlocked_at = (
            profile.partner_unlocked_at or datetime.now(timezone.utc)
        )


async def _create_local_accrual_from_bitrix(
    db: AsyncSession,
    *,
    purchase: AppReferralPurchase,
    raw_accrual: dict[str, Any],
) -> AppReferralAccrual | None:
    beneficiary_bitrix_user_id = int(
        raw_accrual.get("beneficiary_user_id") or 0
    )
    level = int(raw_accrual.get("level") or 0)
    if beneficiary_bitrix_user_id <= 0 or level <= 0:
        return None

    raw_beneficiary = raw_accrual.get("beneficiary")
    raw_beneficiary = (
        raw_beneficiary if isinstance(raw_beneficiary, dict) else {}
    )
    beneficiary_email = optional_str(raw_beneficiary.get("email"))
    beneficiary_user_id = (
        await db.execute(
            select(ReferralProfile.user_id)
            .where(
                ReferralProfile.bitrix_user_id == beneficiary_bitrix_user_id
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if beneficiary_user_id is None:
        beneficiary_user_id = await _local_user_id_for_email(
            db,
            beneficiary_email,
        )
    beneficiary = (
        await db.get(User, beneficiary_user_id)
        if beneficiary_user_id is not None
        else None
    )
    if beneficiary is not None and beneficiary.email:
        beneficiary_email = beneficiary.email
    eligibility = raw_accrual.get("eligibility")
    eligibility = eligibility if isinstance(eligibility, dict) else {}
    row = AppReferralAccrual(
        purchase_id=purchase.id,
        beneficiary_user_id=beneficiary_user_id,
        beneficiary_bitrix_user_id=beneficiary_bitrix_user_id,
        beneficiary_email=beneficiary_email,
        beneficiary_name=(
            optional_str(
                " ".join(
                    part
                    for part in (
                        getattr(beneficiary, "name", ""),
                        getattr(beneficiary, "surname", ""),
                    )
                    if part
                )
            )
            if beneficiary is not None
            else optional_str(raw_beneficiary.get("name"))
        ),
        bitrix_accrual_id=(
            int(raw_accrual["id"]) if raw_accrual.get("id") else None
        ),
        referral_bitrix_user_id=int(
            raw_accrual.get("referral_user_id") or 0
        ),
        level=level,
        buyer_discount_percent=Decimal(
            str(raw_accrual.get("buyer_discount_percent") or 0)
        ),
        referrer_discount_percent=Decimal(
            str(raw_accrual.get("referrer_discount_percent") or 0)
        ),
        commission_percent=Decimal(str(raw_accrual.get("percent") or 0)),
        commission_amount=Decimal(str(raw_accrual.get("amount") or 0)),
        currency=str(raw_accrual.get("currency") or purchase.currency),
        status=str(raw_accrual.get("status") or "pending"),
        reason=optional_str(raw_accrual.get("reason")),
        eligibility_snapshot=eligibility,
    )
    db.add(row)
    return row


async def _create_app_calculation(
    db: AsyncSession,
    *,
    order: Order,
    user: User,
    promo: str | None,
    amount: Decimal,
    paid_at: datetime,
    client: BitrixPromoClient | None,
) -> AppReferralPurchase:
    attached_promo = optional_str(user.promo_code)
    locally_participates = bool(
        promo
        and attached_promo
        and promo.casefold() == attached_promo.casefold()
    )
    calculation = _local_calculation(
        order=order,
        promo=promo,
        amount=amount,
        paid_at=paid_at,
        participates_in_program=locally_participates,
    )
    if promo and client is not None:
        try:
            calculation = await client.quote_referral_accrual(
                external_order_id=order.order_code or str(order.id),
                user_email=user.email or "",
                promo=promo,
                amount=str(amount),
                currency=order.currency,
                paid_at=paid_at.isoformat(),
            )
        except Exception as error:
            calculation["quote_error"] = str(error)[:500]
            logger.exception(
                "Could not pre-calculate Bitrix partner accrual order_id=%s",
                order.id,
            )
    participates_in_program = bool(
        calculation.get("participates_in_program")
        if calculation.get("participates_in_program") is not None
        else calculation.get("referrer_user_id")
        or locally_participates
    )
    calculation["participates_in_program"] = participates_in_program
    period_start, period_end = _period_bounds(paid_at)
    buyer = calculation.get("buyer")
    buyer = buyer if isinstance(buyer, dict) else {}
    purchase = AppReferralPurchase(
        order_id=order.id,
        buyer_user_id=user.id,
        external_order_id=order.order_code or str(order.id),
        bitrix_buyer_user_id=int(buyer["user_id"]) if buyer.get("user_id") else None,
        promo_code=promo,
        amount=amount,
        currency=order.currency,
        paid_at=paid_at,
        period_start=period_start,
        period_end=period_end,
        bitrix_sync_status="pending",
        calculation_snapshot=calculation,
    )
    db.add(purchase)
    await db.flush()
    await _increment_local_purchase_progress(
        db,
        user=user,
        order_id=order.id,
        amount=amount,
        participates_in_program=participates_in_program,
    )

    accruals = calculation.get("accruals")
    if isinstance(accruals, list):
        for raw_accrual in accruals:
            if not isinstance(raw_accrual, dict):
                continue
            beneficiary = raw_accrual.get("beneficiary")
            beneficiary = beneficiary if isinstance(beneficiary, dict) else {}
            eligibility = raw_accrual.get("eligibility")
            eligibility = eligibility if isinstance(eligibility, dict) else {}
            beneficiary_email = optional_str(beneficiary.get("email"))
            beneficiary_user_id = await _local_user_id_for_email(db, beneficiary_email)
            db.add(
                AppReferralAccrual(
                    purchase_id=purchase.id,
                    beneficiary_user_id=beneficiary_user_id,
                    beneficiary_bitrix_user_id=int(beneficiary.get("user_id") or 0),
                    beneficiary_email=beneficiary_email,
                    beneficiary_name=optional_str(beneficiary.get("name")),
                    referral_bitrix_user_id=int(raw_accrual.get("referral_user_id") or 0),
                    level=int(raw_accrual.get("level") or 0),
                    buyer_discount_percent=Decimal(
                        str(raw_accrual.get("referral_discount_percent") or 0)
                    ),
                    referrer_discount_percent=Decimal(
                        str(raw_accrual.get("referrer_discount_percent") or 0)
                    ),
                    commission_percent=Decimal(str(raw_accrual.get("percent") or 0)),
                    commission_amount=Decimal(str(raw_accrual.get("amount") or 0)),
                    currency=order.currency,
                    status=str(eligibility.get("status") or "pending"),
                    reason=optional_str(eligibility.get("reason")),
                    eligibility_snapshot=eligibility,
                )
            )
    await db.commit()
    return await _purchase_for_order(db, order.id) or purchase


async def _ensure_app_calculation(
    db: AsyncSession,
    *,
    order: Order,
    user: User,
    promo: str | None,
    amount: Decimal,
    paid_at: datetime,
    client: BitrixPromoClient | None,
) -> AppReferralPurchase:
    existing = await _purchase_for_order(db, order.id)
    if existing is not None:
        return existing
    try:
        return await _create_app_calculation(
            db,
            order=order,
            user=user,
            promo=promo,
            amount=amount,
            paid_at=paid_at,
            client=client,
        )
    except IntegrityError:
        await db.rollback()
        race_winner = await _purchase_for_order(db, order.id)
        if race_winner is None:
            raise
        return race_winner


async def _sync_purchase_progress_to_bitrix(
    db: AsyncSession,
    *,
    purchase: AppReferralPurchase,
    user: User,
    client: BitrixPromoClient,
) -> dict[str, Any]:
    if purchase.status == "reversed":
        return {
            "outcome": "already_reversed",
            "purchase_id": purchase.id,
        }
    if purchase.status == "reversal_pending":
        return await _sync_partner_reversal_to_bitrix(
            db,
            purchase=purchase,
            client=client,
        )
    if purchase.bitrix_sync_status == "synced":
        return {
            "outcome": "already_synced",
            "purchase_id": purchase.id,
        }

    try:
        result = await client.record_paid_purchase(
            external_order_id=purchase.external_order_id,
            user_email=user.email or "",
            promo=purchase.promo_code,
            amount=str(purchase.amount),
            currency=purchase.currency,
            paid_at=purchase.paid_at.isoformat(),
        )
    except BitrixPromoError as error:
        purchase.bitrix_sync_status = "failed"
        purchase.sync_error = f"{error.code}: {error.message_en}"[:500]
        await db.commit()
        raise

    bitrix_purchase = result.get("purchase")
    bitrix_purchase = bitrix_purchase if isinstance(bitrix_purchase, dict) else {}
    if bitrix_purchase.get("id"):
        purchase.bitrix_purchase_id = int(bitrix_purchase["id"])
    if bitrix_purchase.get("user_id") and purchase.bitrix_buyer_user_id is None:
        purchase.bitrix_buyer_user_id = int(bitrix_purchase["user_id"])
    if bitrix_purchase.get("coupon_id"):
        purchase.bitrix_coupon_id = int(bitrix_purchase["coupon_id"])
    if bitrix_purchase.get("discount_id"):
        purchase.bitrix_discount_id = int(bitrix_purchase["discount_id"])
    if bitrix_purchase.get("coupon_use_count_before") is not None:
        purchase.coupon_use_count_before = int(
            bitrix_purchase["coupon_use_count_before"]
        )
    if bitrix_purchase.get("coupon_use_count_after") is not None:
        purchase.coupon_use_count_after = int(
            bitrix_purchase["coupon_use_count_after"]
        )
    if bitrix_purchase.get("program") is not None:
        calculation_snapshot = dict(purchase.calculation_snapshot or {})
        calculation_snapshot["participates_in_program"] = (
            str(bitrix_purchase["program"]) == "combined"
        )
        purchase.calculation_snapshot = calculation_snapshot

    local_accruals_by_level = {row.level: row for row in purchase.accruals}
    bitrix_accruals = result.get("accruals")
    if isinstance(bitrix_accruals, list):
        for bitrix_accrual in bitrix_accruals:
            if not isinstance(bitrix_accrual, dict):
                continue
            level = int(bitrix_accrual.get("level") or 0)
            local_accrual = local_accruals_by_level.get(level)
            if local_accrual is None:
                local_accrual = await _create_local_accrual_from_bitrix(
                    db,
                    purchase=purchase,
                    raw_accrual=bitrix_accrual,
                )
                if local_accrual is None:
                    continue
                local_accruals_by_level[level] = local_accrual
            if bitrix_accrual.get("id"):
                local_accrual.bitrix_accrual_id = int(bitrix_accrual["id"])
            if bitrix_accrual.get("status"):
                local_accrual.status = str(bitrix_accrual["status"])
            if bitrix_accrual.get("buyer_discount_percent") is not None:
                local_accrual.buyer_discount_percent = Decimal(
                    str(bitrix_accrual["buyer_discount_percent"])
                )
            if bitrix_accrual.get("referrer_discount_percent") is not None:
                local_accrual.referrer_discount_percent = Decimal(
                    str(bitrix_accrual["referrer_discount_percent"])
                )
            if bitrix_accrual.get("percent") is not None:
                local_accrual.commission_percent = Decimal(
                    str(bitrix_accrual["percent"])
                )
            if bitrix_accrual.get("amount") is not None:
                local_accrual.commission_amount = Decimal(
                    str(bitrix_accrual["amount"])
                )
            local_accrual.reason = optional_str(bitrix_accrual.get("reason"))
            eligibility = bitrix_accrual.get("eligibility")
            if isinstance(eligibility, dict):
                local_accrual.eligibility_snapshot = eligibility

    assignment = result.get("assignment")
    assignment = assignment if isinstance(assignment, dict) else {}
    if (
        purchase.promo_code
        and str(assignment.get("outcome") or "")
        in {"attached", "changed", "unchanged", "firm_promo"}
    ):
        user.promo_code = purchase.promo_code
    await _apply_remote_purchase_progress(
        db,
        purchase=purchase,
        progress=(
            result.get("purchase_progress")
            if isinstance(result.get("purchase_progress"), dict)
            else None
        ),
    )
    await refresh_program_profile_from_bitrix(
        db,
        user=user,
        client=client,
    )
    purchase.bitrix_sync_status = "synced"
    purchase.bitrix_synced_at = datetime.now(timezone.utc)
    purchase.sync_error = None
    await db.commit()
    return result


async def _sync_partner_reversal_to_bitrix(
    db: AsyncSession,
    *,
    purchase: AppReferralPurchase,
    client: BitrixPromoClient,
) -> dict[str, Any]:
    try:
        result = await client.reverse_paid_purchase(
            external_order_id=purchase.external_order_id,
        )
    except BitrixPromoError as error:
        if error.code != "purchase_not_found":
            purchase.bitrix_sync_status = "failed"
            purchase.sync_error = f"{error.code}: {error.message_en}"[:500]
            await db.commit()
            raise
        result = {
            "outcome": "remote_purchase_not_found",
            "external_order_id": purchase.external_order_id,
        }
        legacy_purchase = None
        buyer_user_id = getattr(purchase, "buyer_user_id", None)
        order_id = getattr(purchase, "order_id", None)
        if order_id is not None and hasattr(db, "execute"):
            legacy_purchase = (
                await db.execute(
                    select(BonusProgramPurchase.id).where(
                        BonusProgramPurchase.order_id == order_id
                    )
                )
            ).scalar_one_or_none()
        if (
            legacy_purchase is None
            and buyer_user_id is not None
            and hasattr(db, "execute")
            and _purchase_participates_in_program(purchase)
        ):
            profile = (
                await db.execute(
                    select(ReferralProfile)
                    .where(ReferralProfile.user_id == buyer_user_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if profile is not None:
                profile.referral_discount_base_total = quantize_money(
                    max(
                        Decimal("0.00"),
                        profile.referral_discount_base_total - purchase.amount,
                    )
                )
                refresh_profile_discount(profile, has_promo_code=True)

    purchase.status = "reversed"
    purchase.reversed_at = datetime.now(timezone.utc)
    purchase.bitrix_sync_status = "synced"
    purchase.bitrix_synced_at = datetime.now(timezone.utc)
    purchase.sync_error = None
    for accrual in purchase.accruals:
        accrual.status = "rejected"
        accrual.reason = "order_reversed"
    await _apply_remote_purchase_progress(
        db,
        purchase=purchase,
        progress=(
            result.get("purchase_progress")
            if isinstance(result.get("purchase_progress"), dict)
            else None
        ),
    )
    buyer_user_id = getattr(purchase, "buyer_user_id", None)
    if buyer_user_id is not None and hasattr(db, "get"):
        user = await db.get(User, buyer_user_id)
        if user is not None:
            await refresh_program_profile_from_bitrix(
                db,
                user=user,
                client=client,
            )
    await db.commit()
    return result


async def _reverse_bonus_program_purchase(
    db: AsyncSession,
    *,
    purchase: BonusProgramPurchase,
) -> dict[str, Any]:
    if purchase.status == "reversed":
        return {"outcome": "already_reversed", "purchase_id": purchase.id}
    profile = (
        await db.execute(
            select(ReferralProfile)
            .where(ReferralProfile.user_id == purchase.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if profile is not None:
        profile.referral_discount_base_total = quantize_money(
            max(
                Decimal("0.00"),
                profile.referral_discount_base_total - purchase.amount,
            )
        )
        refresh_profile_discount(profile)
    purchase.status = "reversed"
    purchase.reversed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"outcome": "reversed", "purchase_id": purchase.id}


async def reverse_paid_order_reward(
    db: AsyncSession,
    *,
    order: Order,
) -> dict[str, Any] | None:
    legacy_result: dict[str, Any] | None = None
    bonus_purchase = (
        await db.execute(
            select(BonusProgramPurchase)
            .where(BonusProgramPurchase.order_id == order.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if bonus_purchase is not None:
        legacy_result = await _reverse_bonus_program_purchase(
            db,
            purchase=bonus_purchase,
        )

    purchase = await _purchase_for_order(db, order.id)
    if purchase is None:
        if legacy_result is None:
            return None
        return {
            "storage": "legacy_app_bonus",
            "bitrix_written": False,
            **legacy_result,
        }
    if purchase.status == "reversed":
        return {
            "storage": "app_mirror_and_bitrix",
            "outcome": "already_reversed",
            "purchase_id": purchase.id,
        }
    purchase.status = "reversal_pending"
    purchase.bitrix_sync_status = "pending"
    purchase.sync_error = None
    await db.commit()
    if not bitrix_promo_configured():
        if (
            legacy_result is None
            and purchase.buyer_user_id is not None
            and _purchase_participates_in_program(purchase)
        ):
            profile = (
                await db.execute(
                    select(ReferralProfile)
                    .where(
                        ReferralProfile.user_id == purchase.buyer_user_id
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if profile is not None:
                profile.referral_discount_base_total = quantize_money(
                    max(
                        Decimal("0.00"),
                        profile.referral_discount_base_total - purchase.amount,
                    )
                )
                refresh_profile_discount(profile, has_promo_code=True)
        purchase.status = "reversed"
        purchase.reversed_at = datetime.now(timezone.utc)
        purchase.bitrix_sync_status = "not_configured"
        purchase.sync_error = "Bitrix promo integration is not configured"
        for accrual in purchase.accruals:
            accrual.status = "rejected"
            accrual.reason = "order_reversed"
        await db.commit()
        return {
            "storage": "app_mirror",
            "outcome": "reversed_locally",
            "purchase_id": purchase.id,
            "bitrix_written": False,
        }

    result = await _sync_partner_reversal_to_bitrix(
        db,
        purchase=purchase,
        client=BitrixPromoClient(),
    )

    return {
        "storage": "app_mirror_and_bitrix",
        "outcome": str(result.get("outcome") or "reversed"),
        "purchase_id": purchase.id,
        "bitrix": result,
    }


async def sync_paid_order_referral_to_app(
    db: AsyncSession,
    *,
    order: Order,
) -> dict[str, Any] | None:
    payment_status = (order.payment_status or "").strip().lower()
    if order.is_canceled or payment_status == "refunded":
        return await reverse_paid_order_reward(db, order=order)
    if not order.is_paid:
        return None

    user = await db.get(User, order.user_id)
    if user is None or not user.email:
        logger.warning("Skipping app referral calculation without customer email order_id=%s", order.id)
        return None

    amount = _rewardable_order_amount(order)
    if amount <= 0:
        logger.info("Skipping zero-value reward progress order_id=%s", order.id)
        return None

    await ensure_unified_reward_program(db, user=user)
    promo = _paid_order_promo(order)
    paid_at = order.payment_paid_at or order.updated_at or datetime.now(timezone.utc)
    client = BitrixPromoClient() if bitrix_promo_configured() else None
    purchase = await _ensure_app_calculation(
        db,
        order=order,
        user=user,
        promo=promo,
        amount=amount,
        paid_at=paid_at,
        client=client,
    )
    if client is None:
        purchase.bitrix_sync_status = "not_configured"
        purchase.sync_error = "Bitrix promo integration is not configured"
        await db.commit()
        logger.warning(
            "Paid order stored locally until Bitrix is configured order_id=%s",
            order.id,
        )
        return {
            "storage": "app_mirror",
            "purchase_id": purchase.id,
            "accrual_count": len(purchase.accruals),
            "bitrix_written": False,
        }

    bitrix_result = await _sync_purchase_progress_to_bitrix(
        db,
        purchase=purchase,
        user=user,
        client=client,
    )
    logger.info(
        "Paid order reward progress stored order_id=%s accruals=%s bitrix_outcome=%s",
        order.id,
        len(purchase.accruals),
        bitrix_result.get("outcome"),
    )
    return {
        "storage": "app_mirror_and_bitrix",
        "purchase_id": purchase.id,
        "accrual_count": len(purchase.accruals),
        "bitrix": bitrix_result,
    }


async def sync_paid_order_referral_to_app_safe(
    db: AsyncSession,
    *,
    order: Order,
) -> dict[str, Any] | None:
    try:
        return await sync_paid_order_referral_to_app(db, order=order)
    except Exception:
        await db.rollback()
        logger.exception("Could not store app referral calculation order_id=%s", order.id)
        return None


async def retry_unsynced_app_referral_purchases(
    db: AsyncSession,
    *,
    limit: int = 50,
    retry_after_minutes: int = 5,
) -> dict[str, int]:
    if not bitrix_promo_configured():
        return {"processed": 0, "synced": 0, "failed": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(1, retry_after_minutes)
    )
    rows = list(
        (
            await db.execute(
                select(AppReferralPurchase, User)
                .options(selectinload(AppReferralPurchase.accruals))
                .join(User, User.id == AppReferralPurchase.buyer_user_id)
                .where(
                    AppReferralPurchase.bitrix_sync_status.in_(
                        ("pending", "failed", "not_configured")
                    ),
                    AppReferralPurchase.status.in_(
                        ("posted", "reversal_pending")
                    ),
                    AppReferralPurchase.updated_at <= cutoff,
                )
                .order_by(AppReferralPurchase.id)
                .limit(max(1, min(limit, 500)))
            )
        ).all()
    )
    client = BitrixPromoClient()
    synced = 0
    failed = 0
    for purchase, user in rows:
        try:
            if purchase.status == "reversal_pending":
                await _sync_partner_reversal_to_bitrix(
                    db,
                    purchase=purchase,
                    client=client,
                )
            else:
                await _sync_purchase_progress_to_bitrix(
                    db,
                    purchase=purchase,
                    user=user,
                    client=client,
                )
            synced += 1
        except BitrixPromoError:
            failed += 1
            logger.exception(
                "Could not retry Bitrix purchase progress purchase_id=%s",
                purchase.id,
            )
        except Exception:
            failed += 1
            await db.rollback()
            logger.exception(
                "Unexpected retry failure for Bitrix purchase progress purchase_id=%s",
                purchase.id,
            )
            break
    return {
        "processed": synced + failed,
        "synced": synced,
        "failed": failed,
    }


async def backfill_missing_paid_order_rewards(
    db: AsyncSession,
    *,
    limit: int = 50,
) -> dict[str, int]:
    orders = list(
        (
            await db.execute(
                select(Order)
                .outerjoin(
                    AppReferralPurchase,
                    AppReferralPurchase.order_id == Order.id,
                )
                .where(
                    Order.is_paid.is_(True),
                    Order.is_canceled.is_(False),
                    func.coalesce(Order.payment_status, "").notin_(
                        ("refunded", "canceled", "error")
                    ),
                    AppReferralPurchase.id.is_(None),
                )
                .order_by(Order.id)
                .limit(max(1, min(limit, 500)))
            )
        ).scalars().all()
    )
    synced = 0
    failed = 0
    for order in orders:
        try:
            result = await sync_paid_order_referral_to_app(db, order=order)
            if result is not None:
                synced += 1
        except Exception:
            failed += 1
            await db.rollback()
            logger.exception(
                "Could not backfill paid order reward progress order_id=%s",
                order.id,
            )
    return {
        "processed": len(orders),
        "synced": synced,
        "failed": failed,
    }


async def finalize_closed_app_referral_accruals(
    db: AsyncSession,
    *,
    limit: int = 200,
) -> dict[str, int]:
    if not bitrix_promo_configured():
        return {"processed": 0, "approved": 0, "rejected": 0, "failed": 0}

    rows = list(
        (
            await db.execute(
                select(AppReferralAccrual)
                .join(AppReferralPurchase)
                .options(selectinload(AppReferralAccrual.purchase))
                .where(
                    AppReferralAccrual.status == "pending",
                    AppReferralPurchase.period_end <= date.today(),
                )
                .order_by(AppReferralAccrual.id)
                .limit(max(1, min(limit, 1000)))
            )
        ).scalars().all()
    )
    client = BitrixPromoClient()
    approved = 0
    rejected = 0
    failed = 0
    for row in rows:
        try:
            eligibility = await client.referral_eligibility(
                period=row.purchase.period_start.strftime("%Y-%m"),
                bitrix_user_id=row.beneficiary_bitrix_user_id,
                user_email=row.beneficiary_email,
            )
            row.status = str(eligibility.get("status") or "pending")
            row.reason = optional_str(eligibility.get("reason"))
            row.eligibility_snapshot = eligibility
            if row.status == "approved":
                approved += 1
            elif row.status == "rejected":
                rejected += 1
        except BitrixPromoError:
            failed += 1
            logger.exception("Could not finalize app referral accrual id=%s", row.id)
    if rows:
        await db.commit()
    return {
        "processed": len(rows) - failed,
        "approved": approved,
        "rejected": rejected,
        "failed": failed,
    }
