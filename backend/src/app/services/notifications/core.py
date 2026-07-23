import logging

from datetime import datetime, timedelta
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import NOTIFICATION_ABANDONED_CART_AFTER_HOURS, NOTIFICATION_ABANDONED_CART_COOLDOWN_HOURS, NOTIFICATION_BATCH_SIZE, NOTIFICATION_INACTIVE_CUSTOMER_AFTER_DAYS, NOTIFICATION_INACTIVE_CUSTOMER_COOLDOWN_DAYS, NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD, NOTIFICATION_REVIEW_REMINDER_AFTER_DAYS, ufa_now
from src.app.services.push_notifications import send_push_to_user, send_push_to_users
from src.database.models import AdminMarketingAutomation, Basket, BasketItem, CommunityMessage, CommunityNotificationEvent, FavouredProduct, NotificationDispatch, Order, OrderItem, Review, StockNotificationSubscription, UserPushToken, Variant

log = logging.getLogger(__name__)

DISPATCH_TYPE_RESTOCK = "restock"
DISPATCH_TYPE_INACTIVE_CUSTOMER = "inactive_customer"
DISPATCH_TYPE_ABANDONED_CART = "abandoned_cart"
DISPATCH_TYPE_REVIEW_REMINDER = "review_reminder"
DISPATCH_TYPE_AI_REPLY = "ai_reply"
DISPATCH_TYPE_COMMUNITY_MESSAGE = "community_message"


class _MessageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=500)
    deep_link: str | None = Field(default=None, max_length=500)

    @field_validator("deep_link")
    @classmethod
    def internal_deep_link(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.startswith("/") or normalized.startswith("//"):
            raise ValueError("Deep link must be an internal app path")
        return normalized


class _InactiveSettings(_MessageSettings):
    after_days: int = Field(ge=7, le=365)
    cooldown_days: int = Field(ge=1, le=365)


class _AbandonedCartSettings(_MessageSettings):
    after_hours: int = Field(ge=1, le=720)
    cooldown_hours: int = Field(ge=1, le=720)


class _ReviewSettings(_MessageSettings):
    after_days: int = Field(ge=1, le=365)


DEFAULT_AUTOMATION_SETTINGS: dict[str, dict[str, Any]] = {
    "restock": {"title": "Товар снова в наличии", "body": "Вариант {variant_name} снова в наличии.", "deep_link": None},
    "inactive_customer": {
        "title": "Мы соскучились",
        "body": "Давно не было заказов. Загляните, у нас есть новинки для вас.",
        "deep_link": None,
        "after_days": NOTIFICATION_INACTIVE_CUSTOMER_AFTER_DAYS,
        "cooldown_days": NOTIFICATION_INACTIVE_CUSTOMER_COOLDOWN_DAYS,
    },
    "abandoned_cart": {
        "title": "Корзина ждет вас",
        "body": "Вы добавили товары в корзину, но не завершили заказ.",
        "deep_link": None,
        "after_hours": NOTIFICATION_ABANDONED_CART_AFTER_HOURS,
        "cooldown_hours": NOTIFICATION_ABANDONED_CART_COOLDOWN_HOURS,
    },
    "review_reminder": {
        "title": "Поделитесь отзывом",
        "body": "Прошел месяц после заказа. Оцените препарат и оставьте отзыв.",
        "deep_link": None,
        "after_days": NOTIFICATION_REVIEW_REMINDER_AFTER_DAYS,
    },
}


def normalize_marketing_automation_settings(code: str, value: dict[str, Any] | None) -> dict[str, Any]:
    if code not in DEFAULT_AUTOMATION_SETTINGS:
        raise ValueError("Unsupported marketing automation")
    merged = {**DEFAULT_AUTOMATION_SETTINGS[code], **(value or {})}
    model: type[_MessageSettings]
    if code == "inactive_customer":
        model = _InactiveSettings
    elif code == "abandoned_cart":
        model = _AbandonedCartSettings
    elif code == "review_reminder":
        model = _ReviewSettings
    else:
        model = _MessageSettings
    return model.model_validate(merged).model_dump()


def _automation_data(data: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    if settings.get("deep_link"):
        return {**data, "deep_link": settings["deep_link"]}
    return data


def _normalize_stock(stock: int | None) -> int: return max(0, int(stock or 0))
def _is_low_stock(stock: int | None) -> bool: return _normalize_stock(stock) <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD

async def _was_notification_sent_recently(session: AsyncSession, *, user_id: int, dispatch_type: str, dedupe_key: str, cutoff_at: datetime) -> bool:
    last_sent_at = (await session.execute(select(func.max(NotificationDispatch.sent_at)).where(NotificationDispatch.user_id == user_id, NotificationDispatch.type == dispatch_type, NotificationDispatch.dedupe_key == dedupe_key))).scalar_one()
    if last_sent_at is None: return False
    return last_sent_at >= cutoff_at


async def _was_notification_sent_ever(session: AsyncSession, *, user_id: int, dispatch_type: str, dedupe_key: str) -> bool:
    existing_id = (await session.execute(select(NotificationDispatch.id).where( NotificationDispatch.user_id == user_id, NotificationDispatch.type == dispatch_type, NotificationDispatch.dedupe_key == dedupe_key).limit(1))).scalar_one_or_none()
    return existing_id is not None


async def _record_dispatch(session: AsyncSession, *, user_id: int, dispatch_type: str, dedupe_key: str, payload_json: dict[str, Any], sent_at: datetime) -> None:
    session.add(NotificationDispatch(user_id=user_id, type=dispatch_type, dedupe_key=dedupe_key, payload_json=payload_json, sent_at=sent_at))
    await session.flush()


async def _send_and_record(session: AsyncSession, *, user_id: int, title: str, body: str, data: dict[str, Any], dispatch_type: str, dedupe_key: str, sent_at: datetime) -> bool:
    sent = await send_push_to_user(session, user_id=user_id, title=title, body=body, data=data)
    if not sent: return False
    await _record_dispatch(session, user_id=user_id, dispatch_type=dispatch_type, dedupe_key=dedupe_key, payload_json=data, sent_at=sent_at)
    return True


async def activate_stock_notifications_for_favourite_product(session: AsyncSession, *, user_id: int, product_id: int) -> int:
    variants = list((await session.execute(select(Variant).where(Variant.product_id == product_id, Variant.archived.is_(False)).order_by(Variant.id.asc()))).scalars().all())
    if not variants: return 0

    variant_ids = [variant.id for variant in variants]
    existing_subscriptions = list((await session.execute(select(StockNotificationSubscription).where(StockNotificationSubscription.user_id == user_id, StockNotificationSubscription.variant_id.in_(variant_ids)))).scalars().all())
    subscriptions_by_variant_id = {subscription.variant_id: subscription for subscription in existing_subscriptions}

    changed_count = 0
    for variant in variants:
        current_stock = _normalize_stock(variant.stock)
        subscription = subscriptions_by_variant_id.get(variant.id)

        if subscription is None:
            session.add(StockNotificationSubscription(user_id=user_id, variant_id=variant.id, is_active=True, last_seen_stock=current_stock, notified_at=None))
            changed_count += 1
            continue

        # Favouriting a product means listening to all its variants.
        subscription.is_active = True
        subscription.last_seen_stock = current_stock
        subscription.notified_at = None
        changed_count += 1

    if changed_count: await session.commit()
    return changed_count


async def deactivate_stock_notifications_for_favourite_product(session: AsyncSession, *, user_id: int, product_id: int) -> int:
    subscriptions = list((await session.execute(select(StockNotificationSubscription).join(Variant, Variant.id == StockNotificationSubscription.variant_id).where(StockNotificationSubscription.user_id == user_id, Variant.product_id == product_id, Variant.archived.is_(False), StockNotificationSubscription.is_active.is_(True)))).scalars().all())
    for subscription in subscriptions: subscription.is_active = False
    if subscriptions: await session.commit()
    return len(subscriptions)


async def sync_favourite_stock_notification_subscriptions(session: AsyncSession) -> int:
    stmt = (
        select(FavouredProduct.user_id, Variant, StockNotificationSubscription)
        .join(Variant, Variant.product_id == FavouredProduct.product_id)
        .outerjoin(
            StockNotificationSubscription,
            (StockNotificationSubscription.user_id == FavouredProduct.user_id)
            & (StockNotificationSubscription.variant_id == Variant.id),
        )
        .where(
            Variant.archived.is_(False),
            Variant.stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD,
            (StockNotificationSubscription.id.is_(None)) | (StockNotificationSubscription.is_active.is_(False)),
        )
        .order_by(FavouredProduct.id.asc(), Variant.id.asc())
        .limit(NOTIFICATION_BATCH_SIZE)
    )
    rows = (await session.execute(stmt)).all()

    synced_count = 0
    for user_id, variant, subscription in rows:
        current_stock = _normalize_stock(variant.stock)
        if subscription is None: session.add(StockNotificationSubscription(user_id=int(user_id), variant_id=variant.id, is_active=True, last_seen_stock=current_stock, notified_at=None))
        else:
            subscription.is_active = True
            subscription.last_seen_stock = current_stock
            subscription.notified_at = None

        synced_count += 1

    if synced_count: await session.flush()
    return synced_count


async def process_restock_notifications(session: AsyncSession, *, now: datetime | None = None, settings: dict[str, Any] | None = None) -> int:
    current_time = now or ufa_now()
    normalized = normalize_marketing_automation_settings("restock", settings)
    await sync_favourite_stock_notification_subscriptions(session)

    rows = (await session.execute(select(StockNotificationSubscription, Variant).join(Variant, Variant.id == StockNotificationSubscription.variant_id).where(StockNotificationSubscription.is_active.is_(True), StockNotificationSubscription.last_seen_stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD, Variant.archived.is_(False), Variant.stock > StockNotificationSubscription.last_seen_stock).order_by(StockNotificationSubscription.id.asc()).limit(NOTIFICATION_BATCH_SIZE))).all()

    sent_count = 0
    for subscription, variant in rows:
        sent = await _send_and_record(session, user_id=subscription.user_id, title=normalized["title"], body=normalized["body"].replace("{variant_name}", variant.name), data=_automation_data({"type": "restock", "variant_id": variant.id, "variant_name": variant.name, "product_id": variant.product_id, }, normalized), dispatch_type=DISPATCH_TYPE_RESTOCK, dedupe_key=f"variant:{variant.id}", sent_at=current_time)
        if not sent: continue

        subscription.is_active = False
        subscription.last_seen_stock = _normalize_stock(variant.stock)
        subscription.notified_at = current_time
        sent_count += 1

    low_stock_rows = (await session.execute(select(StockNotificationSubscription, Variant).join(Variant, Variant.id == StockNotificationSubscription.variant_id).where(StockNotificationSubscription.is_active.is_(True), Variant.archived.is_(False), Variant.stock <= NOTIFICATION_RESTOCK_LOW_STOCK_THRESHOLD, Variant.stock < StockNotificationSubscription.last_seen_stock).order_by(StockNotificationSubscription.id.asc()).limit(NOTIFICATION_BATCH_SIZE))).all()
    for subscription, variant in low_stock_rows: subscription.last_seen_stock = _normalize_stock(variant.stock)
    await session.commit()
    return sent_count


async def process_inactive_customer_notifications(session: AsyncSession, *, now: datetime | None = None, settings: dict[str, Any] | None = None) -> int:
    current_time = now or ufa_now()
    normalized = normalize_marketing_automation_settings("inactive_customer", settings)
    inactive_cutoff = current_time - timedelta(days=normalized["after_days"])
    cooldown_cutoff = current_time - timedelta(days=normalized["cooldown_days"])

    last_paid_subquery = (select(Order.user_id.label("user_id"), func.max(Order.payment_paid_at).label("last_paid_at")).where(Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.payment_paid_at.is_not(None)).group_by(Order.user_id).subquery())
    rows = (await session.execute(select(last_paid_subquery.c.user_id, last_paid_subquery.c.last_paid_at).where(last_paid_subquery.c.last_paid_at <= inactive_cutoff).order_by(last_paid_subquery.c.last_paid_at.asc()).limit(NOTIFICATION_BATCH_SIZE))).all()

    sent_count = 0
    for user_id, _last_paid_at in rows:
        already_sent = await _was_notification_sent_recently(session, user_id=int(user_id), dispatch_type=DISPATCH_TYPE_INACTIVE_CUSTOMER, dedupe_key="inactive_customer", cutoff_at=cooldown_cutoff)
        if already_sent: continue

        sent = await _send_and_record(session, user_id=int(user_id), title=normalized["title"], body=normalized["body"], data=_automation_data({"type": "inactive_customer"}, normalized), dispatch_type=DISPATCH_TYPE_INACTIVE_CUSTOMER, dedupe_key="inactive_customer", sent_at=current_time)
        if sent: sent_count += 1

    await session.commit()
    return sent_count


async def process_abandoned_cart_notifications(session: AsyncSession, *, now: datetime | None = None, settings: dict[str, Any] | None = None) -> int:
    current_time = now or ufa_now()
    normalized = normalize_marketing_automation_settings("abandoned_cart", settings)
    abandoned_cutoff = current_time - timedelta(hours=normalized["after_hours"])
    cooldown_cutoff = current_time - timedelta(hours=normalized["cooldown_hours"])

    rows = (await session.execute(select(Basket.user_id, Basket.updated_at).join(BasketItem, BasketItem.basket_id == Basket.id).where(Basket.updated_at <= abandoned_cutoff).group_by(Basket.id).order_by(Basket.updated_at.asc()).limit(NOTIFICATION_BATCH_SIZE))).all()

    sent_count = 0
    for user_id, basket_updated_at in rows:
        has_paid_order_after_basket = (await session.execute(select(Order.id).where(Order.user_id == int(user_id), Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.payment_paid_at.is_not(None), Order.payment_paid_at > basket_updated_at).limit(1))).scalar_one_or_none() is not None
        if has_paid_order_after_basket: continue
        already_sent = await _was_notification_sent_recently(session, user_id=int(user_id), dispatch_type=DISPATCH_TYPE_ABANDONED_CART, dedupe_key="abandoned_cart", cutoff_at=cooldown_cutoff)
        if already_sent: continue
        sent = await _send_and_record(session, user_id=int(user_id), title=normalized["title"], body=normalized["body"], data=_automation_data({"type": "abandoned_cart"}, normalized), dispatch_type=DISPATCH_TYPE_ABANDONED_CART, dedupe_key="abandoned_cart", sent_at=current_time)
        if sent: sent_count += 1

    await session.commit()
    return sent_count


async def process_review_reminders(session: AsyncSession, *, now: datetime | None = None, settings: dict[str, Any] | None = None) -> int:
    current_time = now or ufa_now()
    normalized = normalize_marketing_automation_settings("review_reminder", settings)
    review_cutoff = current_time - timedelta(days=normalized["after_days"])

    rows = (await session.execute(select(Order.user_id, OrderItem.product_id, func.max(Order.payment_paid_at).label("last_paid_at")).join(OrderItem, OrderItem.order_id == Order.id).where(Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.payment_paid_at.is_not(None), Order.payment_paid_at <= review_cutoff).group_by(Order.user_id, OrderItem.product_id).order_by(func.max(Order.payment_paid_at).asc()).limit(NOTIFICATION_BATCH_SIZE))).all()
    sent_count = 0
    for user_id, product_id, _ in rows:
        has_review = (await session.execute(select(Review.id).where(Review.user_id == int(user_id), Review.product_id == int(product_id)).limit(1))).scalar_one_or_none() is not None
        if has_review: continue

        already_sent = await _was_notification_sent_ever(session, user_id=int(user_id), dispatch_type=DISPATCH_TYPE_REVIEW_REMINDER, dedupe_key=f"product:{int(product_id)}")
        if already_sent:continue

        sent = await _send_and_record(session, user_id=int(user_id), title=normalized["title"], body=normalized["body"], data=_automation_data({"type": "review_reminder", "product_id": int(product_id), }, normalized), dispatch_type=DISPATCH_TYPE_REVIEW_REMINDER, dedupe_key=f"product:{int(product_id)}", sent_at=current_time)
        if sent: sent_count += 1

    await session.commit()
    return sent_count


async def process_community_message_notifications(session: AsyncSession, *, now: datetime | None = None) -> int:
    current_time = now or ufa_now()
    events = list((await session.execute(
        select(CommunityNotificationEvent)
        .where(
            CommunityNotificationEvent.sent_at.is_(None),
            (CommunityNotificationEvent.next_attempt_at.is_(None)) | (CommunityNotificationEvent.next_attempt_at <= current_time),
        )
        .order_by(CommunityNotificationEvent.id.asc())
        .limit(NOTIFICATION_BATCH_SIZE)
        .with_for_update(skip_locked=True)
        .options(
            selectinload(CommunityNotificationEvent.message).selectinload(CommunityMessage.author),
            selectinload(CommunityNotificationEvent.message).selectinload(CommunityMessage.topic),
            selectinload(CommunityNotificationEvent.message).selectinload(CommunityMessage.attachments),
        )
    )).scalars().all())
    if not events:
        return 0

    registered_user_ids = [int(user_id) for user_id in (await session.execute(
        select(UserPushToken.user_id).distinct().order_by(UserPushToken.user_id.asc())
    )).scalars().all()]
    processed_count = 0
    for event in events:
        message = event.message
        if message.deleted_at is not None:
            event.sent_at = current_time
            event.last_error = None
            processed_count += 1
            continue
        recipient_ids = [user_id for user_id in registered_user_ids if user_id != message.app_user_id]
        author_name = message.author.full_name if message.author else "Участник сообщества"
        preview = " ".join((message.text or "").split())
        if not preview:
            preview = "Отправил(а) вложение" if message.attachments else "Новое сообщение"
        data = {
            "type": DISPATCH_TYPE_COMMUNITY_MESSAGE,
            "topic_id": message.topic_id,
            "message_id": message.id,
        }
        try:
            await send_push_to_users(
                session,
                user_ids=recipient_ids,
                title=message.topic.name,
                body=f"{author_name}: {preview[:180]}",
                data=data,
                channel_id="community_messages",
            )
            event.sent_at = current_time
            event.last_error = None
            processed_count += 1
        except Exception as exc:
            event.attempts += 1
            event.last_error = str(exc)[:1000]
            retry_seconds = min(5 * (2 ** min(event.attempts - 1, 6)), 300)
            event.next_attempt_at = current_time + timedelta(seconds=retry_seconds)
            log.exception("Community push delivery failed message_id=%s attempt=%s", message.id, event.attempts)

    await session.commit()
    return processed_count


async def run_notification_processors_once(session: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    current_time = now or ufa_now()
    processors = {
        "restock": process_restock_notifications,
        "inactive_customer": process_inactive_customer_notifications,
        "abandoned_cart": process_abandoned_cart_notifications,
        "review_reminder": process_review_reminders,
    }
    automation_rows = {
        row.code: row
        for row in (await session.execute(
            select(AdminMarketingAutomation).where(AdminMarketingAutomation.code.in_(processors))
        )).scalars().all()
    }
    results: dict[str, int] = {}
    for code, processor in processors.items():
        automation = automation_rows.get(code)
        if automation is not None and not automation.is_enabled:
            results[code] = 0
            continue
        try:
            processed = await processor(session, now=current_time, settings=automation.settings_json if automation is not None else None)
        except Exception as error:
            if automation is not None:
                automation.last_run_at = current_time
                automation.last_error = (str(error) or error.__class__.__name__)[:2000]
                await session.commit()
            raise
        results[code] = processed
        if automation is not None:
            automation.last_run_at = current_time
            automation.last_result_json = {"processed": processed}
            automation.last_error = None
            await session.commit()
    return results


async def send_ai_reply_notification(session: AsyncSession, *, user_id: int, chat_id: int, message_id: int) -> None:
    try:
        await _send_and_record(session, user_id=user_id, title="Новый ответ от AI-эксперта", body="Мы подготовили ответ в чате.", data={"type": "ai_reply", "chat_id": chat_id, "message_id": message_id, }, dispatch_type=DISPATCH_TYPE_AI_REPLY, dedupe_key=f"message:{message_id}", sent_at=ufa_now())
        await session.commit()

    except Exception:
        await session.rollback()
        log.exception("Failed to send AI reply notification for user_id=%s message_id=%s", user_id, message_id)
