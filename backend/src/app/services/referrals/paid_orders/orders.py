from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import BonusProgramPurchase, Order, ReferralProfile, User
from src.integrations.bitrix_promo import BitrixPromoClient, bitrix_promo_configured
from src.app.services.benefits.loyalty import grant_order_cashback_safe, reverse_order_cashback_safe
from src.app.services.notifications.core import send_reward_program_choice_notification
from src.app.services.referrals.calculations import quantize_money
from src.app.services.referrals.profile import refresh_profile_discount
from src.app.services.referrals.program import ensure_default_reward_program, normalize_reward_program
from .common import logger
from .calculations import _ensure_app_calculation, _paid_order_promo, _paid_order_promo_discount_percent, _purchase_for_order, _purchase_participates_in_program, _rewardable_order_amount
from .remote import _sync_partner_reversal_to_bitrix, _sync_purchase_progress_to_bitrix
from .bonus import _record_bonus_program_purchase, _reverse_bonus_program_purchase


async def reverse_paid_order_reward(db: AsyncSession, *, order: Order,) -> dict[str, Any] | None:
    order_id = order.id
    try: cashback_result = await reverse_order_cashback_safe(db, order=order)
    except Exception:
        await db.rollback()
        await db.refresh(order)
        cashback_result = {"outcome": "reversal_failed"}
        logger.exception("Could not reverse order cashback order_id=%s", order_id)
    legacy_result: dict[str, Any] | None = None
    bonus_purchase = (await db.execute(select(BonusProgramPurchase).where(BonusProgramPurchase.order_id == order.id).with_for_update())).scalar_one_or_none()
    if bonus_purchase is not None: legacy_result = await _reverse_bonus_program_purchase(db, purchase=bonus_purchase,)

    purchase = await _purchase_for_order(db, order.id)
    if purchase is None:
        if legacy_result is None and cashback_result is None: return None
        if legacy_result is None: return {"storage": "moysklad_bonus", "cashback": cashback_result,}
        return {
            "storage": "legacy_app_bonus",
            "bitrix_written": False,
            "cashback": cashback_result,
            **legacy_result,
        }
    if purchase.status == "reversed":
        return {
            "storage": "app_mirror_and_bitrix",
            "outcome": "already_reversed",
            "purchase_id": purchase.id,
            "cashback": cashback_result,
        }
    purchase.status = "reversal_pending"
    purchase.bitrix_sync_status = "pending"
    purchase.sync_error = None
    await db.commit()
    if not bitrix_promo_configured():
        if (legacy_result is None and purchase.buyer_user_id is not None and _purchase_participates_in_program(purchase)):
            profile = (await db.execute(select(ReferralProfile).where(ReferralProfile.user_id == purchase.buyer_user_id).with_for_update())).scalar_one_or_none()
            if profile is not None:
                profile.referral_discount_base_total = quantize_money(max(Decimal("0.00"), profile.referral_discount_base_total - purchase.amount,))
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
            "cashback": cashback_result,
        }

    result = await _sync_partner_reversal_to_bitrix(db, purchase=purchase, client=BitrixPromoClient(),)

    return {
        "storage": "app_mirror_and_bitrix",
        "outcome": str(result.get("outcome") or "reversed"),
        "purchase_id": purchase.id,
        "cashback": cashback_result,
        "bitrix": result,
    }


async def sync_paid_order_referral_to_app(db: AsyncSession, *, order: Order,) -> dict[str, Any] | None:
    payment_status = (order.payment_status or "").strip().lower()
    if order.is_canceled or payment_status == "refunded": return await reverse_paid_order_reward(db, order=order)
    if not order.is_paid: return None

    user = await db.get(User, order.user_id)
    if user is None: return None

    amount = _rewardable_order_amount(order)
    if amount <= 0:
        logger.info("Skipping zero-value reward progress order_id=%s", order.id)
        return None

    profile = await ensure_default_reward_program(db, user=user)
    reward_program = normalize_reward_program(profile.reward_program) or "bonus"
    promo = _paid_order_promo(order)
    buyer_discount_percent = _paid_order_promo_discount_percent(order, promo=promo,)
    paid_at = order.payment_paid_at or order.updated_at or datetime.now(timezone.utc)

    bonus_result: dict[str, Any] | None = None
    if reward_program == "bonus" and not promo:
        bonus_result = await _record_bonus_program_purchase(db, order=order, user=user, amount=amount, paid_at=paid_at,)
        try: await grant_order_cashback_safe(db, order=order, user=user)
        except Exception:
            await db.rollback()
            logger.exception(
                "Could not grant order cashback order_id=%s user_id=%s",
                order.id,
                user.id,
            )
        if bonus_result.get("selection_unlocked"): await send_reward_program_choice_notification(db, user_id=user.id)
        return {
            "storage": "app_bonus_only",
            "bitrix_written": False,
            **bonus_result,
        }

    if not promo:
        logger.info(
            "Skipping referral progress without an applied referrer promo order_id=%s",
            order.id,
        )
        return {"storage": "none", "outcome": "promo_required"}
    if not user.email:
        logger.warning("Skipping app referral calculation without customer email order_id=%s", order.id)
        if bonus_result is not None:
            return {
                "storage": "app_bonus_only",
                "bitrix_written": False,
                "referral_outcome": "email_required",
                **bonus_result,
            }
        return None

    client = BitrixPromoClient() if bitrix_promo_configured() else None
    purchase = await _ensure_app_calculation(db, order=order, user=user, promo=promo, amount=amount, paid_at=paid_at, client=client, buyer_discount_percent=buyer_discount_percent,)
    if client is None:
        purchase.bitrix_sync_status = "not_configured"
        purchase.sync_error = "Bitrix promo integration is not configured"
        await db.commit()
        logger.warning(
            "Paid order stored locally until Bitrix is configured order_id=%s",
            order.id,
        )
        return {
            "storage": "app_bonus_and_mirror" if bonus_result is not None else "app_mirror",
            "purchase_id": purchase.id,
            "accrual_count": len(purchase.accruals),
            "bitrix_written": False,
            "bonus": bonus_result,
        }

    bitrix_result = await _sync_purchase_progress_to_bitrix(db, purchase=purchase, user=user, client=client,)
    logger.info(
        "Paid order reward progress stored order_id=%s accruals=%s bitrix_outcome=%s",
        order.id,
        len(purchase.accruals),
        bitrix_result.get("outcome"),
    )
    return {
        "storage": (
            "app_bonus_mirror_and_bitrix"
            if bonus_result is not None
            else "app_mirror_and_bitrix"
        ),
        "purchase_id": purchase.id,
        "accrual_count": len(purchase.accruals),
        "bitrix": bitrix_result,
        "bonus": bonus_result,
    }


async def sync_paid_order_referral_to_app_safe(db: AsyncSession, *, order: Order,) -> dict[str, Any] | None:
    order_id = order.id
    try: return await sync_paid_order_referral_to_app(db, order=order)
    except Exception:
        await db.rollback()
        logger.exception("Could not store app referral calculation order_id=%s", order_id)
        return None
    finally:
        # A handled integration failure may roll back and expire the caller's order.
        if inspect(order).expired_attributes: await db.refresh(order)
