import logging
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from config import NOTIFICATION_BATCH_SIZE, ufa_now
from src.app.services.benefits import app_welcome as promo
from src.app.services.push_notifications import send_push_to_users
from src.database.models import LoyaltyBonusCredit as Credit, NotificationDispatch as Dispatch, UserPushToken

log = logging.getLogger(__name__)

TITLES = (
    "Вам начислены 1 000 приветственных бонусов",
    "Ваши приветственные бонусы ещё доступны",
    "Напоминаем о приветственных бонусах",
    "Срок приветственных бонусов подходит к концу",
    "Последние 24 часа для приветственных бонусов",
)


def reminder_copy(credit, balance, slot):
    deadline = credit.expires_at.astimezone(promo.MOSCOW).strftime("%d.%m в %H:%M МСК")
    amount = f"{balance:,.2f}".replace(",", " ").replace(".", ",")
    return {"title": TITLES[slot], "body": f"Остаток: {amount} ₽. До {deadline} ими можно оплатить до 50% стоимости товаров. Доставка оплачивается отдельно."}


async def reminder_lock(db, uid):
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"welcome-push:{uid}", 0))))


async def already_notified(db, credit, slot, date_msk):
    return await db.scalar(select(Dispatch.id).where(Dispatch.user_id == credit.user_id,
        Dispatch.type.in_(("welcome_expiry", "welcome_inapp")),
        (Dispatch.payload_json["date_msk"].as_string() == date_msk)
        | (Dispatch.dedupe_key == f"welcome:{credit.id}:{slot}")).limit(1))


def marker(credit, kind, slot):
    # The unique dispatch constraint includes sent_at; use a stable slot time.
    return dict(user_id=credit.user_id, type=kind, dedupe_key=f"welcome:{credit.id}:{slot}",
                sent_at=credit.available_at + timedelta(days=slot))


async def reserve(db, key, **metadata):
    return await db.scalar(insert(Dispatch).values(**key, payload_json={"state": "reserved", **metadata})
        .on_conflict_do_nothing(constraint="uq_notification_dispatches_user_type_dedupe_sent_at")
        .returning(Dispatch.id))


async def pending_notice(db, user_id):
    credit, balance = await promo.wallet(db, user_id)
    if not balance or credit.earned_at < promo.START:
        return None
    if await db.scalar(select(Dispatch.id).filter_by(**marker(credit, "welcome_alert", 0))):
        return None
    return {"credit_id": credit.id, "amount": credit.points, "expires_at": credit.expires_at}


async def acknowledge_notice(db, user_id, credit_id):
    credit = await db.scalar(select(Credit).filter_by(id=credit_id, user_id=user_id, source_kind=promo.KIND))
    if credit:
        await reserve(db, marker(credit, "welcome_alert", 0), date_msk=ufa_now().astimezone(promo.MOSCOW).date().isoformat())
        await db.commit()


async def claim_in_app_reminder(db, uid):
    credit, balance = await promo.wallet(db, uid)
    if not balance or credit.earned_at < promo.START:
        return None
    now = ufa_now()
    slot = (now - credit.available_at).days
    if not 1 <= slot < len(TITLES):
        return None
    date_msk = now.astimezone(promo.MOSCOW).date().isoformat()
    await reminder_lock(db, uid)
    alert = await db.scalar(select(Dispatch).filter_by(**marker(credit, "welcome_alert", 0)))
    if (not alert or alert.payload_json.get("date_msk") == date_msk
            or await db.scalar(select(UserPushToken.id).where(UserPushToken.user_id == uid).limit(1))
            or await already_notified(db, credit, slot, date_msk)):
        return None
    if not await reserve(db, marker(credit, "welcome_inapp", slot), date_msk=date_msk):
        return None
    await db.commit()
    return reminder_copy(credit, balance, slot)


async def process_welcome_reminders(db, *, now=None):
    scan_start = now or ufa_now()
    eligible = select(Credit.id, Credit.user_id).where(
        Credit.source_kind == promo.KIND, Credit.status == "local", Credit.earned_at >= promo.START,
        Credit.available_at <= scan_start, Credit.expires_at > scan_start,
        select(UserPushToken.id).where(UserPushToken.user_id == Credit.user_id).exists(),
    )
    sent, cursor = 0, 0
    while rows := (await db.execute(eligible.where(Credit.id > cursor).order_by(Credit.id)
                                    .limit(max(1, NOTIFICATION_BATCH_SIZE)))).all():
        for cursor, uid in rows:
            credit, balance = await promo.wallet(db, uid)
            if not balance:
                continue
            clock = now or ufa_now()
            slot = (clock - credit.available_at).days
            if not 0 <= slot < 5 or clock >= credit.expires_at:
                continue
            date_msk = clock.astimezone(promo.MOSCOW).date().isoformat()
            # A token may first appear late in a 24h window. Never send twice
            # on that Moscow calendar day when the next window starts.
            await reminder_lock(db, uid)
            if await already_notified(db, credit, slot, date_msk):
                await db.commit()
                continue
            record_id = await reserve(db, marker(credit, "welcome_expiry", slot), date_msk=date_msk)
            if record_id is None:
                await db.commit()
                continue
            copy = reminder_copy(credit, balance, slot)
            # Shipped clients already support this internal deep-link envelope.
            data = {"type": "admin_campaign", "reason": "welcome_expiry", "deep_link": "/profile-discounts", "day": slot + 1}
            # Claim before contacting Expo. On an ambiguous timeout or crash do
            # not replay the same day's push; never drain missed days in a burst.
            await db.commit()
            try:
                accepted = await send_push_to_users(db, user_ids=[uid], **copy, data=data)
            except Exception:
                await db.rollback()
                log.exception("Unconfirmed welcome push dispatch_id=%s", record_id)
                continue
            if accepted:
                await db.execute(update(Dispatch).where(Dispatch.id == record_id).values(
                    payload_json={"state": "accepted", "date_msk": date_msk, **data}))
                sent += 1
            else:
                await db.execute(delete(Dispatch).where(Dispatch.id == record_id))
            await db.commit()
    await db.commit()
    return sent
