import logging
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from config import NOTIFICATION_BATCH_SIZE, ufa_now
from src.app.services.benefits import app_welcome as promo
from src.app.services.push_notifications import send_push_to_users
from src.database.models import LoyaltyBonusCredit as Credit, NotificationDispatch as Dispatch, UserPushToken

log = logging.getLogger(__name__)


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
        await reserve(db, marker(credit, "welcome_alert", 0))
        await db.commit()


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
            await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"welcome-push:{uid}", 0))))
            if await db.scalar(select(Dispatch.id).where(Dispatch.user_id == uid, Dispatch.type == "welcome_expiry",
                    Dispatch.payload_json["date_msk"].as_string() == date_msk).limit(1)):
                await db.commit()
                continue
            record_id = await reserve(db, marker(credit, "welcome_expiry", slot), date_msk=date_msk)
            if record_id is None:
                await db.commit()
                continue
            deadline = credit.expires_at.astimezone(promo.MOSCOW).strftime("%d.%m в %H:%M МСК")
            title = "Вам начислены 1 000 приветственных бонусов" if slot == 0 else "Приветственные бонусы скоро сгорят"
            amount = f"{balance:,.2f}".replace(",", " ").replace(".", ",")
            body = f"Остаток: {amount} ₽. Используйте до {deadline}: до 50% стоимости товаров."
            # Shipped clients already support this internal deep-link envelope.
            data = {"type": "admin_campaign", "reason": "welcome_expiry", "deep_link": "/profile-discounts", "day": slot + 1}
            # Claim before contacting Expo. On an ambiguous timeout or crash do
            # not replay the same day's push; never drain missed days in a burst.
            await db.commit()
            try:
                accepted = await send_push_to_users(db, user_ids=[uid], title=title, body=body, data=data)
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
