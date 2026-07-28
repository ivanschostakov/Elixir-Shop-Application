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
    Order,
    User,
)
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import optional_str

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


async def _create_app_calculation(
    db: AsyncSession,
    *,
    order: Order,
    user: User,
    promo: str,
    paid_at: datetime,
    client: BitrixPromoClient,
) -> AppReferralPurchase:
    calculation = await client.quote_referral_accrual(
        external_order_id=order.order_code or str(order.id),
        user_email=user.email or "",
        promo=promo,
        amount=str(order.grand_total),
        currency=order.currency,
        paid_at=paid_at.isoformat(),
    )
    period_start, period_end = _period_bounds(paid_at)
    buyer = calculation.get("buyer")
    buyer = buyer if isinstance(buyer, dict) else {}
    purchase = AppReferralPurchase(
        order_id=order.id,
        buyer_user_id=user.id,
        external_order_id=order.order_code or str(order.id),
        bitrix_buyer_user_id=int(buyer["user_id"]) if buyer.get("user_id") else None,
        promo_code=promo,
        amount=Decimal(str(order.grand_total)),
        currency=order.currency,
        paid_at=paid_at,
        period_start=period_start,
        period_end=period_end,
        bitrix_sync_status="pending",
        calculation_snapshot=calculation,
    )
    db.add(purchase)
    await db.flush()

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
    promo: str,
    paid_at: datetime,
    client: BitrixPromoClient,
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

    purchase.bitrix_sync_status = "synced"
    purchase.bitrix_synced_at = datetime.now(timezone.utc)
    purchase.sync_error = None
    await db.commit()
    return result


async def sync_paid_order_referral_to_app(
    db: AsyncSession,
    *,
    order: Order,
) -> dict[str, Any] | None:
    if not bitrix_promo_configured() or not order.is_paid or order.is_canceled:
        return None

    user = await db.get(User, order.user_id)
    if user is None or not user.email:
        logger.warning("Skipping app referral calculation without customer email order_id=%s", order.id)
        return None

    promo = _paid_order_promo(order)
    if not promo:
        return None

    paid_at = order.payment_paid_at or order.updated_at or datetime.now(timezone.utc)
    client = BitrixPromoClient()
    purchase = await _ensure_app_calculation(
        db,
        order=order,
        user=user,
        promo=promo,
        paid_at=paid_at,
        client=client,
    )
    bitrix_result = await _sync_purchase_progress_to_bitrix(
        db,
        purchase=purchase,
        user=user,
        client=client,
    )
    logger.info(
        "App referral calculation stored order_id=%s accruals=%s bitrix_outcome=%s",
        order.id,
        len(purchase.accruals),
        bitrix_result.get("outcome"),
    )
    return {
        "storage": "app",
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
                .join(User, User.id == AppReferralPurchase.buyer_user_id)
                .where(
                    AppReferralPurchase.bitrix_sync_status.in_(("pending", "failed")),
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
