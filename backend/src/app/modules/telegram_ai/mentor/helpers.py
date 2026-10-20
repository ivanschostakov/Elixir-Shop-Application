from datetime import datetime, time, timedelta, timezone
import os
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.profile import Identity
from src.app.modules.telegram_ai.journal import now
from .common import router


def section_enabled(section):
    closed = {x.strip() for x in os.getenv("TELEGRAM_MENTOR_CLOSED_SECTIONS", "").split(",")}
    return section not in closed


def require_section(section):
    if not section_enabled(section): raise HTTPException(403, "Раздел временно отключён")


@router.post("/workout/discard-empty")
async def discard_empty_workout(payload: Identity, db: AsyncSession = Depends(get_db)):
    await lock(db, payload.telegram_user_id)
    rows = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "workout", TelegramAIJournal.status == "active"))).scalars()
    count = 0
    for row in rows:
        if not row.data.get("sets"):
            row.status = "cancelled"
            count += 1
    await db.commit()
    return {"ok": True, "discarded": count}


async def lock(db, uid):
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -uid})


@router.post("/touch")
async def touch(payload: Identity, db: AsyncSession = Depends(get_db)):
    """Record interaction time only, never raw chat or media identifiers."""
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == "last-interaction"))).scalar_one_or_none()
    instant = now()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key="last-interaction", kind="activity", status="confirmed", occurred_at=instant, data={})
        db.add(row)
    row.occurred_at = instant
    from src.app.modules.telegram_ai.reminders import options_for
    rule = await options_for(db, payload.telegram_user_id)
    if rule and rule.data.get("inactivity_days"):
        rule.data = {**rule.data, "next": {**rule.data.get("next", {}),
            "inactivity": (instant+timedelta(days=rule.data["inactivity_days"])).isoformat()}}
    pending = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"])))).scalars())
    for item in pending:
        if item.data.get("reminder_kind") == "inactivity": item.status = "cancelled"
    await db.commit()
    return {"ok": True}


async def owned(db, uid, entry_id, kind=None):
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.id == entry_id, TelegramAIJournal.telegram_user_id == uid).with_for_update())).scalar_one_or_none()
    if row is None or (kind is not None and row.kind != kind): raise HTTPException(404, "Запись не найдена")
    return row


def course_dates(course):
    zone = ZoneInfo(course.timezone)
    day = course.start_date
    while day <= course.end_date:
        scheduled = ((day-course.start_date).days % course.interval_days == 0) if course.interval_days else day.weekday() in course.weekdays
        if scheduled:
            for clock in sorted(course.times): yield datetime.combine(day, time.fromisoformat(clock), zone).astimezone(timezone.utc)
        day += timedelta(days=1)
