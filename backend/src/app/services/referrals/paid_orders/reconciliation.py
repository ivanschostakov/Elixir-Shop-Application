from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.database.models import AppReferralAccrual, AppReferralPurchase, BonusProgramPurchase, Order, User
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError, bitrix_promo_configured
from src.normalize import optional_str
from .common import logger
from .remote import _sync_partner_reversal_to_bitrix, _sync_purchase_progress_to_bitrix
from .orders import sync_paid_order_referral_to_app


async def retry_unsynced_app_referral_purchases(db: AsyncSession, *, limit: int = 50, retry_after_minutes: int = 5,) -> dict[str, int]:
    if not bitrix_promo_configured(): return {"processed": 0, "synced": 0, "failed": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, retry_after_minutes))
    rows = list((await db.execute(select(AppReferralPurchase, User).options(selectinload(AppReferralPurchase.accruals)).join(User, User.id == AppReferralPurchase.buyer_user_id).where(AppReferralPurchase.bitrix_sync_status.in_(("pending", "failed", "not_configured")), AppReferralPurchase.status.in_(("posted", "reversal_pending")), AppReferralPurchase.updated_at <= cutoff,).order_by(AppReferralPurchase.id).limit(max(1, min(limit, 500))))).all())
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


async def backfill_missing_paid_order_rewards(db: AsyncSession, *, limit: int = 50,) -> dict[str, int]:
    orders = list((await db.execute(select(Order).outerjoin(AppReferralPurchase, AppReferralPurchase.order_id == Order.id,).outerjoin(BonusProgramPurchase, BonusProgramPurchase.order_id == Order.id,).where(Order.is_paid.is_(True), Order.is_canceled.is_(False), func.coalesce(Order.payment_status, "").notin_(("refunded", "canceled", "error")), AppReferralPurchase.id.is_(None), BonusProgramPurchase.id.is_(None),).order_by(Order.id).limit(max(1, min(limit, 500))))).scalars().all())
    synced = 0
    failed = 0
    for order in orders:
        try:
            result = await sync_paid_order_referral_to_app(db, order=order)
            if result is not None: synced += 1
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


async def finalize_closed_app_referral_accruals(db: AsyncSession, *, limit: int = 200,) -> dict[str, int]:
    if not bitrix_promo_configured(): return {"processed": 0, "approved": 0, "rejected": 0, "failed": 0}

    rows = list((await db.execute(select(AppReferralAccrual).join(AppReferralPurchase).options(selectinload(AppReferralAccrual.purchase)).where(AppReferralAccrual.status == "pending", AppReferralPurchase.period_end <= date.today(),).order_by(AppReferralAccrual.id).limit(max(1, min(limit, 1000))))).scalars().all())
    client = BitrixPromoClient()
    approved = 0
    rejected = 0
    failed = 0
    for row in rows:
        try:
            eligibility = await client.referral_eligibility(period=row.purchase.period_start.strftime("%Y-%m"), bitrix_user_id=row.beneficiary_bitrix_user_id, user_email=row.beneficiary_email,)
            row.status = str(eligibility.get("status") or "pending")
            row.reason = optional_str(eligibility.get("reason"))
            row.eligibility_snapshot = eligibility
            if row.status == "approved": approved += 1
            elif row.status == "rejected": rejected += 1
        except BitrixPromoError:
            failed += 1
            logger.exception("Could not finalize app referral accrual id=%s", row.id)
    if rows: await db.commit()
    return {
        "processed": len(rows) - failed,
        "approved": approved,
        "rejected": rejected,
        "failed": failed,
    }
