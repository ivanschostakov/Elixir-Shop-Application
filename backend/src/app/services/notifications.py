import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    NOTIFICATION_ABANDONED_CART_AFTER_HOURS,
    NOTIFICATION_ABANDONED_CART_COOLDOWN_HOURS,
    NOTIFICATION_ABANDONED_CART_ENABLED,
    NOTIFICATION_AI_EXPERT_REPLY_ENABLED,
    NOTIFICATION_BATCH_SIZE,
    NOTIFICATION_INACTIVE_CUSTOMER_AFTER_DAYS,
    NOTIFICATION_INACTIVE_CUSTOMER_COOLDOWN_DAYS,
    NOTIFICATION_INACTIVE_CUSTOMER_ENABLED,
    NOTIFICATION_RESTOCK_ENABLED,
    NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD,
    NOTIFICATION_REVIEW_REMINDER_AFTER_DAYS,
    NOTIFICATION_REVIEW_REMINDER_ENABLED,
    NOTIFICATIONS_ENABLED,
    ufa_now,
)
from src.app.services.push_notifications import send_push_to_user
from src.database.models import (
    Basket,
    BasketItem,
    FavouredProduct,
    NotificationDispatch,
    Order,
    OrderItem,
    Review,
    StockNotificationSubscription,
    Variant,
)

log = logging.getLogger(__name__)

DISPATCH_TYPE_RESTOCK = "restock"
DISPATCH_TYPE_INACTIVE_CUSTOMER = "inactive_customer"
DISPATCH_TYPE_ABANDONED_CART = "abandoned_cart"
DISPATCH_TYPE_REVIEW_REMINDER = "review_reminder"
DISPATCH_TYPE_AI_REPLY = "ai_reply"


def _normalize_stock(stock: int | None) -> int:
    return max(0, int(stock or 0))


def _is_low_stock(stock: int | None) -> bool:
    return _normalize_stock(stock) <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD


async def _was_notification_sent_recently(
    session: AsyncSession,
    *,
    user_id: int,
    dispatch_type: str,
    dedupe_key: str,
    cutoff_at: datetime,
) -> bool:
    last_sent_at = (
        await session.execute(
            select(func.max(NotificationDispatch.sent_at)).where(
                NotificationDispatch.user_id == user_id,
                NotificationDispatch.type == dispatch_type,
                NotificationDispatch.dedupe_key == dedupe_key,
            )
        )
    ).scalar_one()
    if last_sent_at is None:
        return False
    return last_sent_at >= cutoff_at


async def _was_notification_sent_ever(
    session: AsyncSession,
    *,
    user_id: int,
    dispatch_type: str,
    dedupe_key: str,
) -> bool:
    existing_id = (
        await session.execute(
            select(NotificationDispatch.id)
            .where(
                NotificationDispatch.user_id == user_id,
                NotificationDispatch.type == dispatch_type,
                NotificationDispatch.dedupe_key == dedupe_key,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return existing_id is not None


async def _record_dispatch(
    session: AsyncSession,
    *,
    user_id: int,
    dispatch_type: str,
    dedupe_key: str,
    payload_json: dict[str, Any],
    sent_at: datetime,
) -> None:
    session.add(
        NotificationDispatch(
            user_id=user_id,
            type=dispatch_type,
            dedupe_key=dedupe_key,
            payload_json=payload_json,
            sent_at=sent_at,
        )
    )
    await session.flush()


async def _send_and_record(
    session: AsyncSession,
    *,
    user_id: int,
    title: str,
    body: str,
    data: dict[str, Any],
    dispatch_type: str,
    dedupe_key: str,
    sent_at: datetime,
) -> bool:
    sent = await send_push_to_user(
        session,
        user_id=user_id,
        title=title,
        body=body,
        data=data,
    )
    if not sent:
        return False

    await _record_dispatch(
        session,
        user_id=user_id,
        dispatch_type=dispatch_type,
        dedupe_key=dedupe_key,
        payload_json=data,
        sent_at=sent_at,
    )
    return True


async def activate_stock_notifications_for_favourite_product(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
) -> int:
    variants = list(
        (
            await session.execute(
                select(Variant)
                .where(Variant.product_id == product_id)
                .order_by(Variant.id.asc())
            )
        )
        .scalars()
        .all()
    )
    if not variants:
        return 0

    variant_ids = [variant.id for variant in variants]
    existing_subscriptions = list(
        (
            await session.execute(
                select(StockNotificationSubscription).where(
                    StockNotificationSubscription.user_id == user_id,
                    StockNotificationSubscription.variant_id.in_(variant_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    subscriptions_by_variant_id = {
        subscription.variant_id: subscription
        for subscription in existing_subscriptions
    }

    changed_count = 0
    for variant in variants:
        current_stock = _normalize_stock(variant.stock)
        subscription = subscriptions_by_variant_id.get(variant.id)

        if subscription is None:
            session.add(
                StockNotificationSubscription(
                    user_id=user_id,
                    variant_id=variant.id,
                    is_active=True,
                    last_seen_stock=current_stock,
                    notified_at=None,
                )
            )
            changed_count += 1
            continue

        # Favouriting a product means listening to all its variants.
        subscription.is_active = True
        subscription.last_seen_stock = current_stock
        subscription.notified_at = None
        changed_count += 1

    if changed_count:
        await session.commit()

    return changed_count


async def deactivate_stock_notifications_for_favourite_product(
    session: AsyncSession,
    *,
    user_id: int,
    product_id: int,
) -> int:
    subscriptions = list(
        (
            await session.execute(
                select(StockNotificationSubscription)
                .join(Variant, Variant.id == StockNotificationSubscription.variant_id)
                .where(
                    StockNotificationSubscription.user_id == user_id,
                    Variant.product_id == product_id,
                    StockNotificationSubscription.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    for subscription in subscriptions:
        subscription.is_active = False

    if subscriptions:
        await session.commit()

    return len(subscriptions)


async def sync_favourite_stock_notification_subscriptions(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(FavouredProduct.user_id, Variant, StockNotificationSubscription)
            .join(Variant, Variant.product_id == FavouredProduct.product_id)
            .outerjoin(
                StockNotificationSubscription,
                (StockNotificationSubscription.user_id == FavouredProduct.user_id)
                & (StockNotificationSubscription.variant_id == Variant.id),
            )
            .where(
                Variant.stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD,
                (StockNotificationSubscription.id.is_(None))
                | (StockNotificationSubscription.is_active.is_(False)),
            )
            .order_by(FavouredProduct.id.asc(), Variant.id.asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    synced_count = 0
    for user_id, variant, subscription in rows:
        current_stock = _normalize_stock(variant.stock)
        if subscription is None:
            session.add(
                StockNotificationSubscription(
                    user_id=int(user_id),
                    variant_id=variant.id,
                    is_active=True,
                    last_seen_stock=current_stock,
                    notified_at=None,
                )
            )
        else:
            subscription.is_active = True
            subscription.last_seen_stock = current_stock
            subscription.notified_at = None
        synced_count += 1

    if synced_count:
        await session.flush()

    return synced_count


async def process_restock_notifications(session: AsyncSession, *, now: datetime | None = None) -> int:
    if not NOTIFICATIONS_ENABLED or not NOTIFICATION_RESTOCK_ENABLED:
        return 0

    current_time = now or ufa_now()
    await sync_favourite_stock_notification_subscriptions(session)

    rows = (
        await session.execute(
            select(StockNotificationSubscription, Variant)
            .join(Variant, Variant.id == StockNotificationSubscription.variant_id)
            .where(
                StockNotificationSubscription.is_active.is_(True),
                StockNotificationSubscription.last_seen_stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD,
                Variant.stock > StockNotificationSubscription.last_seen_stock,
            )
            .order_by(StockNotificationSubscription.id.asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    sent_count = 0
    for subscription, variant in rows:
        sent = await _send_and_record(
            session,
            user_id=subscription.user_id,
            title="Товар снова в наличии",
            body=f"Вариант {variant.name} снова в наличии.",
            data={
                "type": "restock",
                "variant_id": variant.id,
                "variant_name": variant.name,
                "product_id": variant.product_id,
            },
            dispatch_type=DISPATCH_TYPE_RESTOCK,
            dedupe_key=f"variant:{variant.id}",
            sent_at=current_time,
        )
        if not sent:
            continue

        subscription.is_active = False
        subscription.last_seen_stock = _normalize_stock(variant.stock)
        subscription.notified_at = current_time
        sent_count += 1

    low_stock_rows = (
        await session.execute(
            select(StockNotificationSubscription, Variant)
            .join(Variant, Variant.id == StockNotificationSubscription.variant_id)
            .where(
                StockNotificationSubscription.is_active.is_(True),
                Variant.stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD,
                Variant.stock < StockNotificationSubscription.last_seen_stock,
            )
            .order_by(StockNotificationSubscription.id.asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    for subscription, variant in low_stock_rows:
        subscription.last_seen_stock = _normalize_stock(variant.stock)

    await session.commit()
    return sent_count


async def process_inactive_customer_notifications(session: AsyncSession, *, now: datetime | None = None) -> int:
    if not NOTIFICATIONS_ENABLED or not NOTIFICATION_INACTIVE_CUSTOMER_ENABLED:
        return 0

    current_time = now or ufa_now()
    inactive_cutoff = current_time - timedelta(days=NOTIFICATION_INACTIVE_CUSTOMER_AFTER_DAYS)
    cooldown_cutoff = current_time - timedelta(days=NOTIFICATION_INACTIVE_CUSTOMER_COOLDOWN_DAYS)

    last_paid_subquery = (
        select(
            Order.user_id.label("user_id"),
            func.max(Order.payment_paid_at).label("last_paid_at"),
        )
        .where(
            Order.is_paid.is_(True),
            Order.is_canceled.is_(False),
            Order.payment_paid_at.is_not(None),
        )
        .group_by(Order.user_id)
        .subquery()
    )

    rows = (
        await session.execute(
            select(last_paid_subquery.c.user_id, last_paid_subquery.c.last_paid_at)
            .where(last_paid_subquery.c.last_paid_at <= inactive_cutoff)
            .order_by(last_paid_subquery.c.last_paid_at.asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    sent_count = 0
    for user_id, _last_paid_at in rows:
        already_sent = await _was_notification_sent_recently(
            session,
            user_id=int(user_id),
            dispatch_type=DISPATCH_TYPE_INACTIVE_CUSTOMER,
            dedupe_key="inactive_customer",
            cutoff_at=cooldown_cutoff,
        )
        if already_sent:
            continue

        sent = await _send_and_record(
            session,
            user_id=int(user_id),
            title="Мы соскучились",
            body="Давно не было заказов. Загляните, у нас есть новинки для вас.",
            data={"type": "inactive_customer"},
            dispatch_type=DISPATCH_TYPE_INACTIVE_CUSTOMER,
            dedupe_key="inactive_customer",
            sent_at=current_time,
        )
        if sent:
            sent_count += 1

    await session.commit()
    return sent_count


async def process_abandoned_cart_notifications(session: AsyncSession, *, now: datetime | None = None) -> int:
    if not NOTIFICATIONS_ENABLED or not NOTIFICATION_ABANDONED_CART_ENABLED:
        return 0

    current_time = now or ufa_now()
    abandoned_cutoff = current_time - timedelta(hours=NOTIFICATION_ABANDONED_CART_AFTER_HOURS)
    cooldown_cutoff = current_time - timedelta(hours=NOTIFICATION_ABANDONED_CART_COOLDOWN_HOURS)

    rows = (
        await session.execute(
            select(Basket.user_id, Basket.updated_at)
            .join(BasketItem, BasketItem.basket_id == Basket.id)
            .where(Basket.updated_at <= abandoned_cutoff)
            .group_by(Basket.id)
            .order_by(Basket.updated_at.asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    sent_count = 0
    for user_id, basket_updated_at in rows:
        has_paid_order_after_basket = (
            await session.execute(
                select(Order.id)
                .where(
                    Order.user_id == int(user_id),
                    Order.is_paid.is_(True),
                    Order.is_canceled.is_(False),
                    Order.payment_paid_at.is_not(None),
                    Order.payment_paid_at > basket_updated_at,
                )
                .limit(1)
            )
        ).scalar_one_or_none() is not None
        if has_paid_order_after_basket:
            continue

        already_sent = await _was_notification_sent_recently(
            session,
            user_id=int(user_id),
            dispatch_type=DISPATCH_TYPE_ABANDONED_CART,
            dedupe_key="abandoned_cart",
            cutoff_at=cooldown_cutoff,
        )
        if already_sent:
            continue

        sent = await _send_and_record(
            session,
            user_id=int(user_id),
            title="Корзина ждет вас",
            body="Вы добавили товары в корзину, но не завершили заказ.",
            data={"type": "abandoned_cart"},
            dispatch_type=DISPATCH_TYPE_ABANDONED_CART,
            dedupe_key="abandoned_cart",
            sent_at=current_time,
        )
        if sent:
            sent_count += 1

    await session.commit()
    return sent_count


async def process_review_reminders(session: AsyncSession, *, now: datetime | None = None) -> int:
    if not NOTIFICATIONS_ENABLED or not NOTIFICATION_REVIEW_REMINDER_ENABLED:
        return 0

    current_time = now or ufa_now()
    review_cutoff = current_time - timedelta(days=NOTIFICATION_REVIEW_REMINDER_AFTER_DAYS)

    rows = (
        await session.execute(
            select(
                Order.user_id,
                OrderItem.product_id,
                func.max(Order.payment_paid_at).label("last_paid_at"),
            )
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.is_paid.is_(True),
                Order.is_canceled.is_(False),
                Order.payment_paid_at.is_not(None),
                Order.payment_paid_at <= review_cutoff,
            )
            .group_by(Order.user_id, OrderItem.product_id)
            .order_by(func.max(Order.payment_paid_at).asc())
            .limit(NOTIFICATION_BATCH_SIZE)
        )
    ).all()

    sent_count = 0
    for user_id, product_id, _ in rows:
        has_review = (
            await session.execute(
                select(Review.id)
                .where(
                    Review.user_id == int(user_id),
                    Review.product_id == int(product_id),
                )
                .limit(1)
            )
        ).scalar_one_or_none() is not None
        if has_review:
            continue

        already_sent = await _was_notification_sent_ever(
            session,
            user_id=int(user_id),
            dispatch_type=DISPATCH_TYPE_REVIEW_REMINDER,
            dedupe_key=f"product:{int(product_id)}",
        )
        if already_sent:
            continue

        sent = await _send_and_record(
            session,
            user_id=int(user_id),
            title="Поделитесь отзывом",
            body="Прошел месяц после заказа. Оцените препарат и оставьте отзыв.",
            data={
                "type": "review_reminder",
                "product_id": int(product_id),
            },
            dispatch_type=DISPATCH_TYPE_REVIEW_REMINDER,
            dedupe_key=f"product:{int(product_id)}",
            sent_at=current_time,
        )
        if sent:
            sent_count += 1

    await session.commit()
    return sent_count


async def run_notification_processors_once(session: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    current_time = now or ufa_now()
    results = {
        "restock": await process_restock_notifications(session, now=current_time),
        "inactive_customer": await process_inactive_customer_notifications(session, now=current_time),
        "abandoned_cart": await process_abandoned_cart_notifications(session, now=current_time),
        "review_reminder": await process_review_reminders(session, now=current_time),
    }
    return results


async def send_ai_reply_notification(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    message_id: int,
) -> None:
    if not NOTIFICATIONS_ENABLED or not NOTIFICATION_AI_EXPERT_REPLY_ENABLED:
        return

    try:
        await _send_and_record(
            session,
            user_id=user_id,
            title="Новый ответ от AI-эксперта",
            body="Мы подготовили ответ в чате.",
            data={
                "type": "ai_reply",
                "chat_id": chat_id,
                "message_id": message_id,
            },
            dispatch_type=DISPATCH_TYPE_AI_REPLY,
            dedupe_key=f"message:{message_id}",
            sent_at=ufa_now(),
        )
        await session.commit()
    except Exception:
        await session.rollback()
        log.exception("Failed to send AI reply notification for user_id=%s message_id=%s", user_id, message_id)
