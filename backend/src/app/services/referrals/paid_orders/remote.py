from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import AppReferralPurchase, BonusProgramPurchase, ReferralProfile, User
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError
from src.normalize import optional_str
from src.app.services.referrals.bitrix_sync import refresh_program_profile_from_bitrix
from src.app.services.referrals.calculations import quantize_money
from src.app.services.referrals.profile import refresh_profile_discount
from .calculations import _purchase_participates_in_program
from .progress import _apply_remote_purchase_progress
from .accruals import _create_local_accrual_from_bitrix


async def _sync_purchase_progress_to_bitrix(db: AsyncSession, *, purchase: AppReferralPurchase, user: User, client: BitrixPromoClient,) -> dict[str, Any]:
    if purchase.status == "reversed": return {"outcome": "already_reversed", "purchase_id": purchase.id,}
    if purchase.status == "reversal_pending": return await _sync_partner_reversal_to_bitrix(db, purchase=purchase, client=client,)
    if purchase.bitrix_sync_status == "synced": return {"outcome": "already_synced", "purchase_id": purchase.id,}

    try:
        calculation_snapshot = (purchase.calculation_snapshot if isinstance(purchase.calculation_snapshot, dict) else {})
        raw_buyer_discount_percent = calculation_snapshot.get("buyer_discount_percent")
        result = await client.record_paid_purchase(external_order_id=purchase.external_order_id, user_email=user.email or "", promo=purchase.promo_code, amount=str(purchase.amount), currency=purchase.currency, paid_at=purchase.paid_at.isoformat(), buyer_discount_percent=(str(raw_buyer_discount_percent) if raw_buyer_discount_percent is not None else None),)
    except BitrixPromoError as error:
        purchase.bitrix_sync_status = "failed"
        purchase.sync_error = f"{error.code}: {error.message_en}"[:500]
        await db.commit()
        raise

    bitrix_purchase = result.get("purchase")
    bitrix_purchase = bitrix_purchase if isinstance(bitrix_purchase, dict) else {}
    if bitrix_purchase.get("id"): purchase.bitrix_purchase_id = int(bitrix_purchase["id"])
    if bitrix_purchase.get("user_id") and purchase.bitrix_buyer_user_id is None: purchase.bitrix_buyer_user_id = int(bitrix_purchase["user_id"])
    if bitrix_purchase.get("coupon_id"): purchase.bitrix_coupon_id = int(bitrix_purchase["coupon_id"])
    if bitrix_purchase.get("discount_id"): purchase.bitrix_discount_id = int(bitrix_purchase["discount_id"])
    if bitrix_purchase.get("coupon_use_count_before") is not None: purchase.coupon_use_count_before = int(bitrix_purchase["coupon_use_count_before"])
    if bitrix_purchase.get("coupon_use_count_after") is not None: purchase.coupon_use_count_after = int(bitrix_purchase["coupon_use_count_after"])
    if bitrix_purchase.get("program") is not None:
        calculation_snapshot = dict(purchase.calculation_snapshot or {})
        calculation_snapshot["participates_in_program"] = (str(bitrix_purchase["program"]) == "partner")
        purchase.calculation_snapshot = calculation_snapshot

    local_accruals_by_level = {row.level: row for row in purchase.accruals}
    bitrix_accruals = result.get("accruals")
    if isinstance(bitrix_accruals, list):
        for bitrix_accrual in bitrix_accruals:
            if not isinstance(bitrix_accrual, dict): continue
            level = int(bitrix_accrual.get("level") or 0)
            local_accrual = local_accruals_by_level.get(level)
            if local_accrual is None:
                local_accrual = await _create_local_accrual_from_bitrix(db, purchase=purchase, raw_accrual=bitrix_accrual,)
                if local_accrual is None: continue
                local_accruals_by_level[level] = local_accrual
            if bitrix_accrual.get("id"): local_accrual.bitrix_accrual_id = int(bitrix_accrual["id"])
            if bitrix_accrual.get("status"): local_accrual.status = str(bitrix_accrual["status"])
            if bitrix_accrual.get("buyer_discount_percent") is not None: local_accrual.buyer_discount_percent = Decimal(str(bitrix_accrual["buyer_discount_percent"]))
            if bitrix_accrual.get("referrer_discount_percent") is not None: local_accrual.referrer_discount_percent = Decimal(str(bitrix_accrual["referrer_discount_percent"]))
            if bitrix_accrual.get("percent") is not None: local_accrual.commission_percent = Decimal(str(bitrix_accrual["percent"]))
            if bitrix_accrual.get("amount") is not None: local_accrual.commission_amount = Decimal(str(bitrix_accrual["amount"]))
            local_accrual.reason = optional_str(bitrix_accrual.get("reason"))
            eligibility = bitrix_accrual.get("eligibility")
            if isinstance(eligibility, dict): local_accrual.eligibility_snapshot = eligibility

    assignment = result.get("assignment")
    assignment = assignment if isinstance(assignment, dict) else {}
    if (purchase.promo_code and str(assignment.get("outcome") or "") in {"attached", "changed", "unchanged", "firm_promo"}): user.promo_code = purchase.promo_code
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


async def _sync_partner_reversal_to_bitrix(db: AsyncSession, *, purchase: AppReferralPurchase, client: BitrixPromoClient,) -> dict[str, Any]:
    try: result = await client.reverse_paid_purchase(external_order_id=purchase.external_order_id,)
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
        if order_id is not None and hasattr(db, "execute"): legacy_purchase = (await db.execute(select(BonusProgramPurchase.id).where(BonusProgramPurchase.order_id == order_id))).scalar_one_or_none()
        if (legacy_purchase is None and buyer_user_id is not None and hasattr(db, "execute") and _purchase_participates_in_program(purchase)):
            profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == buyer_user_id).with_for_update())).scalar_one_or_none()
            if profile is not None:
                profile.referral_discount_base_total = quantize_money(max(Decimal("0.00"), profile.referral_discount_base_total - purchase.amount,))
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
