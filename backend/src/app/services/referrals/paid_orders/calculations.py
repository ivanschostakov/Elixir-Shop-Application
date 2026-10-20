from datetime import date, datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.database.models import AppReferralAccrual, AppReferralPurchase, Order, User
from src.integrations.bitrix_promo import BitrixPromoClient
from src.normalize import optional_str
from .common import logger
from .progress import _increment_local_purchase_progress


def _paid_order_promo(order: Order) -> str | None:
    checkout_snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = checkout_snapshot.get("benefits")
    benefits = benefits if isinstance(benefits, dict) else {}
    applications = benefits.get("applications")
    if not isinstance(applications, list): return None

    for application in applications:
        if not isinstance(application, dict): continue
        if code := optional_str(application.get("code")): return code
    return None


def _paid_order_promo_discount_percent(order: Order, *, promo: str | None,) -> Decimal | None:
    if not promo: return None
    checkout_snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = checkout_snapshot.get("benefits")
    benefits = benefits if isinstance(benefits, dict) else {}
    applications = benefits.get("applications")
    if not isinstance(applications, list): return None

    for application in applications:
        if not isinstance(application, dict): continue
        application_code = optional_str(application.get("code"))
        if not application_code or application_code.casefold() != promo.casefold(): continue
        value = application.get("discount_percent")
        if value is None: return None
        try: return max(Decimal("0.00"), Decimal(str(value)))
        except (ArithmeticError, TypeError, ValueError): return None
    return None


def _period_bounds(paid_at: datetime) -> tuple[date, date]:
    period_start = date(paid_at.year, paid_at.month, 1)
    if paid_at.month == 12: return period_start, date(paid_at.year + 1, 1, 1)
    return period_start, date(paid_at.year, paid_at.month + 1, 1)


def _rewardable_order_amount(order: Order) -> Decimal:
    checkout_snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = checkout_snapshot.get("benefits")
    benefits = benefits if isinstance(benefits, dict) else {}
    total_after_discounts = benefits.get("total_after_discounts")
    if total_after_discounts is not None:
        try: return max(Decimal("0.00"), Decimal(str(total_after_discounts)))
        except Exception:
            logger.warning(
                "Could not parse merchandise total from checkout snapshot order_id=%s",
                order.id,
            )

    return max(Decimal("0.00"), Decimal(str(order.grand_total)) - Decimal(str(order.delivery_total)),)


def _purchase_participates_in_program(purchase: AppReferralPurchase) -> bool:
    snapshot = (purchase.calculation_snapshot if isinstance(purchase.calculation_snapshot, dict) else {})
    explicit = snapshot.get("participates_in_program")
    if explicit is not None: return bool(explicit)
    return bool(optional_str(purchase.promo_code))


async def _purchase_for_order(db: AsyncSession, order_id: int,) -> AppReferralPurchase | None:
    return (await db.execute(select(AppReferralPurchase).options(selectinload(AppReferralPurchase.accruals)).where(AppReferralPurchase.order_id == order_id))).scalar_one_or_none()


async def _local_user_id_for_email(db: AsyncSession, email: str | None) -> int | None:
    normalized = optional_str(email)
    if not normalized: return None
    return (await db.execute(select(User.id).where(func.lower(User.email) == normalized.casefold()).limit(1))).scalar_one_or_none()


def _local_calculation(*, order: Order, promo: str | None, amount: Decimal, paid_at: datetime, participates_in_program: bool, buyer_discount_percent: Decimal | None,) -> dict[str, Any]:
    return {
        "storage": "app",
        "bitrix_writes": False,
        "program": "partner",
        "promo": promo,
        "promo_mode": "unresolved" if promo else "none",
        "participates_in_program": participates_in_program,
        "amount": str(amount),
        "currency": order.currency,
        "paid_at": paid_at.isoformat(),
        "buyer_discount_percent": (
            str(buyer_discount_percent)
            if buyer_discount_percent is not None
            else None
        ),
        "accruals": [],
    }


async def _create_app_calculation(db: AsyncSession, *, order: Order, user: User, promo: str | None, amount: Decimal, paid_at: datetime, client: BitrixPromoClient | None, buyer_discount_percent: Decimal | None,) -> AppReferralPurchase:
    attached_promo = optional_str(user.promo_code)
    locally_participates = bool(promo and attached_promo and promo.casefold() == attached_promo.casefold())
    calculation = _local_calculation(order=order, promo=promo, amount=amount, paid_at=paid_at, participates_in_program=locally_participates, buyer_discount_percent=buyer_discount_percent,)
    if promo and client is not None:
        try: calculation = await client.quote_referral_accrual(external_order_id=order.order_code or str(order.id), user_email=user.email or "", promo=promo, amount=str(amount), currency=order.currency, paid_at=paid_at.isoformat(), buyer_discount_percent=(str(buyer_discount_percent) if buyer_discount_percent is not None else None),)
        except Exception as error:
            calculation["quote_error"] = str(error)[:500]
            logger.exception(
                "Could not pre-calculate Bitrix partner accrual order_id=%s",
                order.id,
            )
    if buyer_discount_percent is not None:
        # Preserve the percentage actually charged by the app even when an
        # older remote module does not echo the optional override yet.
        calculation["buyer_discount_percent"] = str(buyer_discount_percent)
    participates_in_program = bool(calculation.get("participates_in_program") if calculation.get("participates_in_program") is not None else calculation.get("referrer_user_id") or locally_participates)
    calculation["participates_in_program"] = participates_in_program
    period_start, period_end = _period_bounds(paid_at)
    buyer = calculation.get("buyer")
    buyer = buyer if isinstance(buyer, dict) else {}
    purchase = AppReferralPurchase(order_id=order.id, buyer_user_id=user.id, external_order_id=order.order_code or str(order.id), bitrix_buyer_user_id=int(buyer["user_id"]) if buyer.get("user_id") else None, promo_code=promo, amount=amount, currency=order.currency, paid_at=paid_at, period_start=period_start, period_end=period_end, bitrix_sync_status="pending", calculation_snapshot=calculation,)
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
            if not isinstance(raw_accrual, dict): continue
            beneficiary = raw_accrual.get("beneficiary")
            beneficiary = beneficiary if isinstance(beneficiary, dict) else {}
            eligibility = raw_accrual.get("eligibility")
            eligibility = eligibility if isinstance(eligibility, dict) else {}
            beneficiary_email = optional_str(beneficiary.get("email"))
            beneficiary_user_id = await _local_user_id_for_email(db, beneficiary_email)
            db.add(AppReferralAccrual(purchase_id=purchase.id, beneficiary_user_id=beneficiary_user_id, beneficiary_bitrix_user_id=int(beneficiary.get("user_id") or 0), beneficiary_email=beneficiary_email, beneficiary_name=optional_str(beneficiary.get("name")), referral_bitrix_user_id=int(raw_accrual.get("referral_user_id") or 0), level=int(raw_accrual.get("level") or 0), buyer_discount_percent=Decimal(str(raw_accrual.get("referral_discount_percent") or 0)), referrer_discount_percent=Decimal(str(raw_accrual.get("referrer_discount_percent") or 0)), commission_percent=Decimal(str(raw_accrual.get("percent") or 0)), commission_amount=Decimal(str(raw_accrual.get("amount") or 0)), currency=order.currency, status=str(eligibility.get("status") or "pending"), reason=optional_str(eligibility.get("reason")), eligibility_snapshot=eligibility,))
    await db.commit()
    return await _purchase_for_order(db, order.id) or purchase


async def _ensure_app_calculation(db: AsyncSession, *, order: Order, user: User, promo: str | None, amount: Decimal, paid_at: datetime, client: BitrixPromoClient | None, buyer_discount_percent: Decimal | None,) -> AppReferralPurchase:
    existing = await _purchase_for_order(db, order.id)
    if existing is not None: return existing
    try: return await _create_app_calculation(db, order=order, user=user, promo=promo, amount=amount, paid_at=paid_at, client=client, buyer_discount_percent=buyer_discount_percent,)
    except IntegrityError:
        await db.rollback()
        race_winner = await _purchase_for_order(db, order.id)
        if race_winner is None: raise
        return race_winner
