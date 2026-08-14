import hashlib
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    LOYALTY_BONUS_LIFETIME_DAYS,
    LOYALTY_EXPIRY_WARNING_DAYS,
    LOYALTY_ORDER_CASHBACK_PERCENT,
    LOYALTY_PHOTO_REVIEW_BONUS_POINTS,
    LOYALTY_TEXT_REVIEW_BONUS_POINTS,
    LOYALTY_WELCOME_BONUS_POINTS,
    MOY_SKLAD_BONUS_PROGRAM_ID,
    ufa_now,
)
from src.database.models import LoyaltyBonusCredit, Order, OrderItem, Review, ReviewAttachment, User
from src.integrations.moysklad.client import MoySkladClient, get_moysklad_client
from src.integrations.moysklad.idempotency import build_counterparty_external_code, build_sync_id
from src.normalize import coerce_uuid, optional_str

from .money import quantize_money
from .moysklad_bonus import MoySkladBonusWallet, get_moysklad_bonus_wallet

logger = logging.getLogger(__name__)

REWARD_MODE_CASHBACK = "cashback"
REWARD_MODE_PROMO = "promo"


def normalize_reward_mode(value: str | None, *, has_entered_code: bool = False) -> str:
    normalized = optional_str(value)
    if normalized in {REWARD_MODE_CASHBACK, REWARD_MODE_PROMO}:
        return normalized
    return REWARD_MODE_PROMO if has_entered_code else REWARD_MODE_CASHBACK


def cashback_points_for_amount(amount: Decimal | int | float | str | None) -> int:
    normalized = quantize_money(amount) or Decimal("0.00")
    percent = max(0, min(100, int(LOYALTY_ORDER_CASHBACK_PERCENT)))
    return max(
        0,
        int((normalized * Decimal(percent) / Decimal("100")).to_integral_value(rounding=ROUND_FLOOR)),
    )


def _external_code(key: str, action: str = "earn") -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return f"elixir-loyalty-{action}-{digest}"


async def _ensure_moysklad_wallet(
    db: AsyncSession,
    *,
    user: User,
    client: MoySkladClient,
) -> MoySkladBonusWallet:
    if not client.is_configured():
        raise RuntimeError("MoySklad is not configured")

    if user.moysklad_counterparty_id is None:
        external_code = build_counterparty_external_code(user_id=user.id)
        counterparty = await client.resolve_or_sync_counterparty(
            existing_counterparty_id=None,
            external_code=external_code,
            sync_id=build_sync_id(scope="counterparty", key=external_code),
            name=" ".join(part for part in (user.name, user.surname) if part).strip() or f"App user {user.id}",
            email=user.email,
            phone=user.phone_number,
            actual_address=None,
        )
        user.moysklad_counterparty_id = counterparty.counterparty_id
        await db.commit()

    wallet = await get_moysklad_bonus_wallet(user.moysklad_counterparty_id, moysklad_client=client)
    if wallet.program_id is not None:
        return wallet

    configured_program_id = coerce_uuid(MOY_SKLAD_BONUS_PROGRAM_ID)
    if configured_program_id is None:
        default_program = await client.get_default_bonus_program()
        configured_program_id = coerce_uuid((default_program or {}).get("id"))
    if configured_program_id is None:
        raise RuntimeError("No active MoySklad bonus program is configured")

    await client.assign_counterparty_bonus_program(user.moysklad_counterparty_id, configured_program_id)
    wallet = await get_moysklad_bonus_wallet(user.moysklad_counterparty_id, moysklad_client=client)
    if wallet.program_id is None:
        raise RuntimeError("MoySklad bonus program could not be assigned")
    return wallet


async def _credit_by_key(db: AsyncSession, key: str) -> LoyaltyBonusCredit | None:
    return (
        await db.execute(
            select(LoyaltyBonusCredit).where(LoyaltyBonusCredit.idempotency_key == key).limit(1)
        )
    ).scalar_one_or_none()


async def sync_loyalty_bonus_credit(
    db: AsyncSession,
    *,
    credit: LoyaltyBonusCredit,
    client: MoySkladClient | None = None,
) -> bool:
    if credit.status == "applied" and credit.moysklad_bonus_transaction_id is not None:
        return True
    user = await db.get(User, credit.user_id)
    if user is None:
        credit.status = "failed"
        credit.sync_error = "User not found"
        await db.commit()
        return False

    moysklad_client = client or get_moysklad_client()
    try:
        wallet = await _ensure_moysklad_wallet(db, user=user, client=moysklad_client)
        if wallet.counterparty_id is None or wallet.program_id is None:
            raise RuntimeError("MoySklad bonus wallet is unavailable")
        transaction = await moysklad_client.resolve_or_create_bonus_transaction(
            counterparty_id=wallet.counterparty_id,
            bonus_program_id=wallet.program_id,
            bonus_points=credit.points,
            transaction_type="EARNING",
            external_code=_external_code(credit.idempotency_key),
            name=f"Начисление бонусов: {credit.source_kind}",
            description=f"Elixir Shop loyalty credit #{credit.id}",
        )
        transaction_id = coerce_uuid(transaction.get("id"))
        if transaction_id is None or transaction.get("applicable") is False:
            raise RuntimeError("MoySklad rejected the bonus credit")
        credit.moysklad_bonus_program_id = wallet.program_id
        credit.moysklad_bonus_transaction_id = transaction_id
        credit.status = "applied"
        credit.sync_error = None
        await db.commit()
        return True
    except Exception as exc:
        await db.rollback()
        persisted = await db.get(LoyaltyBonusCredit, credit.id)
        if persisted is not None:
            persisted.status = "failed"
            persisted.sync_error = (str(exc) or exc.__class__.__name__)[:500]
            await db.commit()
        logger.exception("Could not sync loyalty bonus credit id=%s", credit.id)
        return False


async def create_loyalty_bonus_credit(
    db: AsyncSession,
    *,
    user: User,
    source_kind: str,
    idempotency_key: str,
    points: int,
    earned_at: datetime | None = None,
    order_id: int | None = None,
    review_id: int | None = None,
    sync_immediately: bool = True,
) -> LoyaltyBonusCredit | None:
    normalized_points = max(0, int(points))
    if normalized_points <= 0:
        return None
    existing = await _credit_by_key(db, idempotency_key)
    if existing is not None:
        if sync_immediately and existing.status in {"pending", "failed"}:
            await sync_loyalty_bonus_credit(db, credit=existing)
        return existing

    origin = earned_at or ufa_now()
    credit = LoyaltyBonusCredit(
        user_id=user.id,
        order_id=order_id,
        review_id=review_id,
        source_kind=source_kind,
        idempotency_key=idempotency_key,
        points=normalized_points,
        spent_points=0,
        status="pending",
        earned_at=origin,
        available_at=origin,
        expires_at=origin + timedelta(days=max(1, int(LOYALTY_BONUS_LIFETIME_DAYS))),
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    if sync_immediately:
        await sync_loyalty_bonus_credit(db, credit=credit)
    return credit


async def grant_welcome_bonus_safe(db: AsyncSession, *, user: User) -> LoyaltyBonusCredit | None:
    if user.welcome_bonus_granted_at is not None:
        return await _credit_by_key(db, f"welcome:user:{user.id}")
    credit = await create_loyalty_bonus_credit(
        db,
        user=user,
        source_kind="welcome",
        idempotency_key=f"welcome:user:{user.id}",
        points=LOYALTY_WELCOME_BONUS_POINTS,
        sync_immediately=False,
    )
    user.welcome_bonus_granted_at = ufa_now()
    await db.commit()
    return credit


def _order_benefits(order: Order) -> dict:
    snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    benefits = snapshot.get("benefits")
    return benefits if isinstance(benefits, dict) else {}


async def grant_order_cashback_safe(db: AsyncSession, *, order: Order, user: User) -> LoyaltyBonusCredit | None:
    if not order.is_paid or order.is_canceled:
        return None
    benefits = _order_benefits(order)
    reward_program = benefits.get("reward_program")
    if reward_program != "bonus" and (
        reward_program is not None
        or normalize_reward_mode(
            benefits.get("reward_mode"),
            has_entered_code=bool(benefits.get("entered_code")),
        ) != REWARD_MODE_CASHBACK
    ):
        return None
    points = int(benefits.get("cashback_earned_points") or 0)
    if points <= 0:
        merchandise_total = benefits.get("total_after_discounts")
        if merchandise_total is None:
            merchandise_total = max(Decimal("0.00"), order.grand_total - order.delivery_total)
        points = cashback_points_for_amount(merchandise_total)
    return await create_loyalty_bonus_credit(
        db,
        user=user,
        source_kind="order_cashback",
        idempotency_key=f"cashback:order:{order.id}",
        points=points,
        earned_at=order.payment_paid_at or ufa_now(),
        order_id=order.id,
    )


async def reverse_loyalty_bonus_credit(
    db: AsyncSession,
    *,
    credit: LoyaltyBonusCredit,
    client: MoySkladClient | None = None,
) -> bool:
    if credit.status in {"reversed", "expired"}:
        return True
    if credit.status in {"pending", "failed"} and credit.moysklad_bonus_transaction_id is None:
        credit.status = "reversed"
        credit.reversed_at = ufa_now()
        credit.sync_error = None
        await db.commit()
        return True

    unspent = max(0, credit.points - credit.spent_points)
    if unspent <= 0:
        credit.status = "reversed"
        credit.reversed_at = ufa_now()
        credit.sync_error = None
        await db.commit()
        return True

    user = await db.get(User, credit.user_id)
    moysklad_client = client or get_moysklad_client()
    try:
        if user is None:
            raise RuntimeError("User not found")
        wallet = await _ensure_moysklad_wallet(db, user=user, client=moysklad_client)
        if wallet.counterparty_id is None or wallet.program_id is None:
            raise RuntimeError("MoySklad bonus wallet is unavailable")
        transaction = await moysklad_client.resolve_or_create_bonus_transaction(
            counterparty_id=wallet.counterparty_id,
            bonus_program_id=wallet.program_id,
            bonus_points=unspent,
            transaction_type="SPENDING",
            external_code=_external_code(credit.idempotency_key, "reverse"),
            name="Отмена начисления бонусов",
            description=f"Reversed Elixir Shop loyalty credit #{credit.id}",
        )
        transaction_id = coerce_uuid(transaction.get("id"))
        if transaction_id is None or transaction.get("applicable") is False:
            raise RuntimeError("MoySklad rejected the bonus reversal")
        credit.moysklad_debit_transaction_id = transaction_id
        credit.status = "reversed"
        credit.reversed_at = ufa_now()
        credit.sync_error = None
        await db.commit()
        return True
    except Exception as exc:
        await db.rollback()
        persisted = await db.get(LoyaltyBonusCredit, credit.id)
        if persisted is not None:
            persisted.status = "reversal_pending"
            persisted.sync_error = (str(exc) or exc.__class__.__name__)[:500]
            await db.commit()
        logger.exception("Could not reverse loyalty bonus credit id=%s", credit.id)
        return False


async def reverse_order_cashback_safe(db: AsyncSession, *, order: Order) -> dict[str, object] | None:
    credit = await _credit_by_key(db, f"cashback:order:{order.id}")
    if credit is None:
        return None
    reversed_ok = await reverse_loyalty_bonus_credit(db, credit=credit)
    return {
        "credit_id": credit.id,
        "outcome": "reversed" if reversed_ok else "reversal_pending",
    }


async def grant_review_bonus_safe(db: AsyncSession, *, review: Review, user: User) -> LoyaltyBonusCredit | None:
    has_paid_purchase = (
        await db.execute(
            select(OrderItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.user_id == user.id,
                OrderItem.product_id == review.product_id,
                Order.is_paid.is_(True),
                Order.is_canceled.is_(False),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_paid_purchase is None:
        return None
    attachment_count = int(
        (
            await db.execute(
                select(func.count(ReviewAttachment.id)).where(ReviewAttachment.review_id == review.id)
            )
        ).scalar_one()
        or 0
    )
    has_text = bool(optional_str(review.text))
    if not has_text and attachment_count <= 0:
        return None
    points = LOYALTY_PHOTO_REVIEW_BONUS_POINTS if attachment_count > 0 else LOYALTY_TEXT_REVIEW_BONUS_POINTS
    return await create_loyalty_bonus_credit(
        db,
        user=user,
        source_kind="review_photo" if attachment_count > 0 else "review_text",
        idempotency_key=f"review:user:{user.id}:product:{review.product_id}",
        points=points,
        review_id=review.id,
    )


async def allocate_bonus_spend_to_credits(db: AsyncSession, *, user_id: int, points: int) -> int:
    remaining = max(0, int(points))
    if remaining <= 0:
        return 0
    rows = list(
        (
            await db.execute(
                select(LoyaltyBonusCredit)
                .where(
                    LoyaltyBonusCredit.user_id == user_id,
                    LoyaltyBonusCredit.status == "applied",
                    LoyaltyBonusCredit.expires_at > ufa_now(),
                    LoyaltyBonusCredit.spent_points < LoyaltyBonusCredit.points,
                )
                .order_by(LoyaltyBonusCredit.expires_at.asc(), LoyaltyBonusCredit.id.asc())
                .with_for_update()
            )
        ).scalars().all()
    )
    allocated = 0
    for credit in rows:
        available = max(0, credit.points - credit.spent_points)
        consumed = min(available, remaining)
        credit.spent_points += consumed
        allocated += consumed
        remaining -= consumed
        if remaining <= 0:
            break
    return allocated


async def pending_loyalty_bonus_points(db: AsyncSession, *, user_id: int) -> int:
    value = (
        await db.execute(
            select(func.coalesce(func.sum(LoyaltyBonusCredit.points), 0)).where(
                LoyaltyBonusCredit.user_id == user_id,
                LoyaltyBonusCredit.status.in_(("pending", "failed")),
                LoyaltyBonusCredit.expires_at > ufa_now(),
            )
        )
    ).scalar_one()
    return max(0, int(value or 0))


async def loyalty_bonus_expiration_summary(
    db: AsyncSession,
    *,
    user_id: int,
    now: datetime | None = None,
) -> dict[str, object]:
    current_time = now or ufa_now()
    warning_cutoff = current_time + timedelta(
        days=max(1, int(LOYALTY_EXPIRY_WARNING_DAYS))
    )
    rows = list(
        (
            await db.execute(
                select(LoyaltyBonusCredit)
                .where(
                    LoyaltyBonusCredit.user_id == user_id,
                    LoyaltyBonusCredit.status.in_(("applied", "pending", "failed")),
                    LoyaltyBonusCredit.expires_at > current_time,
                    LoyaltyBonusCredit.spent_points < LoyaltyBonusCredit.points,
                )
                .order_by(LoyaltyBonusCredit.expires_at.asc(), LoyaltyBonusCredit.id.asc())
            )
        ).scalars().all()
    )
    expiring_points = sum(
        max(0, row.points - row.spent_points)
        for row in rows
        if row.expires_at <= warning_cutoff
    )
    return {
        "next_expires_at": rows[0].expires_at if rows else None,
        "expiring_points": expiring_points,
        "warning_days": max(1, int(LOYALTY_EXPIRY_WARNING_DAYS)),
    }


async def sync_pending_loyalty_bonus_credits(db: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    rows = list(
        (
            await db.execute(
                select(LoyaltyBonusCredit)
                .where(LoyaltyBonusCredit.status.in_(("pending", "failed", "reversal_pending")))
                .order_by(LoyaltyBonusCredit.id.asc())
                .limit(max(1, min(limit, 500)))
            )
        ).scalars().all()
    )
    synced = 0
    failed = 0
    for credit in rows:
        if credit.status == "reversal_pending":
            success = await reverse_loyalty_bonus_credit(db, credit=credit)
        else:
            success = await sync_loyalty_bonus_credit(db, credit=credit)
        if success:
            synced += 1
        else:
            failed += 1
    return {"processed": len(rows), "synced": synced, "failed": failed}


async def expire_loyalty_bonus_credits(db: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    now = ufa_now()
    rows = list(
        (
            await db.execute(
                select(LoyaltyBonusCredit)
                .where(
                    LoyaltyBonusCredit.status == "applied",
                    LoyaltyBonusCredit.expires_at <= now,
                )
                .order_by(LoyaltyBonusCredit.expires_at.asc())
                .limit(max(1, min(limit, 500)))
            )
        ).scalars().all()
    )
    expired = 0
    failed = 0
    client = get_moysklad_client()
    for credit in rows:
        unspent = max(0, credit.points - credit.spent_points)
        try:
            if unspent > 0:
                user = await db.get(User, credit.user_id)
                if user is None:
                    raise RuntimeError("User not found")
                wallet = await _ensure_moysklad_wallet(db, user=user, client=client)
                if wallet.counterparty_id is None or wallet.program_id is None:
                    raise RuntimeError("MoySklad bonus wallet is unavailable")
                transaction = await client.resolve_or_create_bonus_transaction(
                    counterparty_id=wallet.counterparty_id,
                    bonus_program_id=wallet.program_id,
                    bonus_points=unspent,
                    transaction_type="SPENDING",
                    external_code=_external_code(credit.idempotency_key, "expire"),
                    name="Сгорание бонусов",
                    description=f"Expired Elixir Shop loyalty credit #{credit.id}",
                )
                credit.moysklad_debit_transaction_id = coerce_uuid(transaction.get("id"))
                if credit.moysklad_debit_transaction_id is None or transaction.get("applicable") is False:
                    raise RuntimeError("MoySklad expiration transaction has no id")
            credit.status = "expired"
            credit.expired_at = now
            credit.sync_error = None
            await db.commit()
            expired += 1
        except Exception as exc:
            await db.rollback()
            persisted = await db.get(LoyaltyBonusCredit, credit.id)
            if persisted is not None:
                persisted.sync_error = (str(exc) or exc.__class__.__name__)[:500]
                await db.commit()
            failed += 1
    return {"processed": len(rows), "expired": expired, "failed": failed}
