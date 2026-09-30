"""Durable Telegram outbox: leases expire; only a delivery ACK marks sent."""
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.ai.companion.schemas import StrictModel
from src.database import get_db
from src.database.models import TelegramAIJournal, TelegramAIReminderSettings
from .profile import Identity
from .journal import now, next_reminder, ReminderUpdate

router = APIRouter(prefix="/reminder")
KINDS = {"morning", "evening", "weekly", "inactivity", "course"}
MESSAGES = {
    "morning": "Утреннее напоминание: можно записать вес.",
    "evening": "Вечернее напоминание: можно подвести итоги дня.",
    "weekly": "Недельный отчёт готов к просмотру в разделе «Прогресс».",
    "inactivity": "Давно не виделись. Продолжим, когда вам будет удобно.",
    "course": "Есть пункт вашего сохранённого расписания. Откройте «Мой курс».",
}
GRACE = {"course": timedelta(minutes=30), "morning": timedelta(hours=12),
         "evening": timedelta(hours=12), "weekly": timedelta(days=1), "inactivity": timedelta(hours=12)}


def expired(data, occurred_at, instant):
    return instant-occurred_at > GRACE[data["reminder_kind"]]


def schedule_changed(previous, current, kind):
    field = "inactivity_days" if kind == "inactivity" else kind
    return previous.get(field) != current.get(field) or previous.get("timezone") != current.get("timezone") or (kind == "weekly" and previous.get("weekday") != current.get("weekday"))


class Options(Identity):
    timezone: str = "Europe/Moscow"
    morning: str | None = None
    evening: str | None = None
    weekly: str | None = None
    weekday: int = Field(default=6, ge=0, le=6)
    inactivity_days: int | None = Field(default=None, ge=1, le=30)
    course: bool = False

    @model_validator(mode="after")
    def validated(self):
        for clock in (self.morning, self.evening, self.weekly):
            ReminderUpdate(telegram_user_id=self.telegram_user_id, timezone=self.timezone, daily_time=clock)
        return self


class Ack(Identity):
    delivery_id: int = Field(gt=0)
    token: str = Field(min_length=32, max_length=32)
    outcome: str


@router.post("/check")
async def check(payload: Ack, db: AsyncSession = Depends(get_db)):
    row = await db.get(TelegramAIJournal, payload.delivery_id)
    allowed = bool(row and row.telegram_user_id == payload.telegram_user_id and row.kind == "reminder"
        and row.status == "leased" and row.data.get("token") == payload.token)
    if allowed and row.data.get("event_id"):
        event = await db.get(TelegramAIJournal, row.data["event_id"])
        allowed = bool(event and event.status == "pending")
        if allowed:
            course = await db.get(TelegramAIJournal, event.data["course_id"])
            allowed = bool(course and course.status == "confirmed")
    if allowed:
        allowed = not expired(row.data, row.occurred_at, now())
    if allowed and not row.data.get("legacy"):
        rule = await options_for(db, payload.telegram_user_id)
        kind = row.data["reminder_kind"]
        field = "inactivity_days" if kind == "inactivity" else kind
        allowed = bool(rule and rule.data.get(field) and row.data.get("schedule") == schedule_signature(rule.data, kind))
    return {"deliver": allowed}


def schedule_signature(settings, kind):
    field = "inactivity_days" if kind == "inactivity" else kind
    return {"value": settings.get(field), "timezone": settings.get("timezone"),
            "weekday": settings.get("weekday") if kind == "weekly" else None,
            "course_since": settings.get("course_since") if kind == "course" else None}


async def options_for(db, uid):
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.request_key == "reminder-options"
    ))).scalar_one_or_none()
    if row:
        return row
    return None


@router.post("/options")
async def options(payload: Options, db: AsyncSession = Depends(get_db)):
    payload.validated()
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -payload.telegram_user_id})
    row = await options_for(db, payload.telegram_user_id)
    instant = now()
    values = payload.model_dump(exclude={"telegram_user_id"})
    previous = row.data if row else {}
    due = {}
    for kind in ("morning", "evening", "weekly"):
        clock = values[kind]
        if clock:
            if previous.get(kind) == clock and previous.get("timezone") == values["timezone"] and previous.get("weekday") == values["weekday"]:
                due[kind] = previous.get("next", {}).get(kind)
            if not due.get(kind):
                due[kind] = scheduled(values, kind, instant).isoformat()
    if values["inactivity_days"]:
        due["inactivity"] = (previous.get("next", {}).get("inactivity")
            if previous.get("inactivity_days") == values["inactivity_days"] else None) or (instant+timedelta(days=values["inactivity_days"])).isoformat()
    values["next"] = due
    if previous.get("inactivity_last_episode"):
        values["inactivity_last_episode"] = previous["inactivity_last_episode"]
    values["course_since"] = previous.get("course_since", instant.isoformat()) if payload.course and previous.get("course") else instant.isoformat()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key="reminder-options",
            kind="reminder_rule", status="active", occurred_at=instant, data={})
        db.add(row)
    row.data = values
    # Keep the legacy daily endpoint and dashboard timezone interoperable.
    legacy = await db.get(TelegramAIReminderSettings, payload.telegram_user_id)
    if legacy is None:
        legacy = TelegramAIReminderSettings(telegram_user_id=payload.telegram_user_id)
        db.add(legacy)
    legacy.timezone = payload.timezone
    legacy.daily_time = None
    legacy.next_at = None
    queued = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"])
    ))).scalars())
    for item in queued:
        kind = item.data["reminder_kind"]
        enabled = values.get("inactivity_days" if kind == "inactivity" else kind)
        if not enabled or schedule_changed(previous, values, kind) or item.data.get("legacy"):
            item.status = "cancelled"
    await db.commit()
    return {"ok": True, **values}


def scheduled(settings, kind, instant):
    target = next_reminder(settings["timezone"], settings[kind], instant)
    if kind == "weekly":
        local = target.astimezone(ZoneInfo(settings["timezone"]))
        local += timedelta(days=(settings["weekday"]-local.weekday()) % 7)
        target = local.astimezone(timezone.utc)
    return target


async def enqueue(db, uid, kind, instant, key, **extra):
    found = (await db.execute(select(TelegramAIJournal.id).where(
        TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.request_key == key
    ))).scalar_one_or_none()
    if found is None:
        db.add(TelegramAIJournal(telegram_user_id=uid, request_key=key, kind="reminder",
            status="pending", occurred_at=instant, data={"reminder_kind": kind, "attempts": 0, **extra}))


async def claim_due(db):
    instant = now()
    # One scheduler transaction at a time; individual deliveries use expiring leases.
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    legacy = list((await db.execute(select(TelegramAIReminderSettings).where(
        TelegramAIReminderSettings.next_at <= instant, TelegramAIReminderSettings.daily_time.is_not(None)
    ).with_for_update())).scalars())
    for row in legacy:
        await enqueue(db, row.telegram_user_id, "evening", row.next_at,
            "reminder:legacy:"+row.next_at.isoformat(), legacy=True)
        row.next_at = next_reminder(row.timezone, row.daily_time, instant)
    rules = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.kind == "reminder_rule", TelegramAIJournal.status == "active"
    ).with_for_update())).scalars())
    for rule in rules:
        data = {**rule.data, "next": {**rule.data.get("next", {})}}
        for kind, value in list(data["next"].items()):
            due_at = datetime.fromisoformat(value)
            if due_at > instant:
                continue
            if kind == "inactivity":
                activity = (await db.execute(select(TelegramAIJournal.occurred_at).where(
                    TelegramAIJournal.telegram_user_id == rule.telegram_user_id,
                    TelegramAIJournal.kind.in_(["activity", "meal", "weight", "workout", "measurement", "wellbeing"]),
                    TelegramAIJournal.status == "confirmed"
                ).order_by(TelegramAIJournal.occurred_at.desc()).limit(1))).scalar_one_or_none()
                activity = activity or rule.occurred_at
                if activity+timedelta(days=data["inactivity_days"]) > instant:
                    data["next"][kind] = (activity+timedelta(days=data["inactivity_days"])).isoformat()
                    continue
                episode = activity.isoformat()
                if data.get("inactivity_last_episode") == episode:
                    continue
                due_at = activity+timedelta(days=data["inactivity_days"])
                value = due_at.isoformat()
                data["inactivity_last_episode"] = episode
            await enqueue(db, rule.telegram_user_id, kind, due_at, f"reminder:{kind}:{value}", schedule=schedule_signature(data, kind))
            following = instant+timedelta(days=data["inactivity_days"]) if kind == "inactivity" else scheduled(data, kind, instant)
            data["next"][kind] = following.isoformat()
        if data.get("course"):
            events = list((await db.execute(select(TelegramAIJournal).where(
                TelegramAIJournal.telegram_user_id == rule.telegram_user_id,
                TelegramAIJournal.kind == "course_event", TelegramAIJournal.status == "pending",
                TelegramAIJournal.occurred_at >= datetime.fromisoformat(data["course_since"]),
                TelegramAIJournal.occurred_at <= instant
            ))).scalars())
            for event in events:
                course = await db.get(TelegramAIJournal, event.data["course_id"])
                if course is None or course.status != "confirmed":
                    continue
                await enqueue(db, rule.telegram_user_id, "course", event.occurred_at,
                    f"reminder:course:{event.id}", event_id=event.id, schedule=schedule_signature(data, "course"))
        rule.data = data
    await db.flush()
    rows = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"]),
        TelegramAIJournal.occurred_at <= instant
    ).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id).with_for_update())).scalars())
    items = []
    for row in rows:
        if expired(row.data, row.occurred_at, instant):
            row.status = "expired"
            row.data = {**row.data, "expired_at": instant.isoformat(), "expiry_reason": "delivery_window_elapsed"}
            continue
        retry = row.data.get("retry_at")
        if retry and datetime.fromisoformat(retry) > instant:
            continue
        if row.data.get("event_id"):
            event = await db.get(TelegramAIJournal, row.data["event_id"])
            if event is None or event.status != "pending":
                row.status = "cancelled"
                continue
            course = await db.get(TelegramAIJournal, event.data["course_id"])
            if course is None or course.status != "confirmed":
                row.status = "cancelled"
                continue
        token = uuid4().hex
        row.data = {**row.data, "token": token, "attempts": row.data.get("attempts", 0)+1,
                    "retry_at": (instant+timedelta(minutes=5)).isoformat()}
        row.status = "leased"
        items.append({"telegram_user_id": row.telegram_user_id, "delivery_id": row.id,
            "token": token, "kind": row.data["reminder_kind"], "text": MESSAGES[row.data["reminder_kind"]]})
        if len(items) >= 50:
            break
    await db.commit()
    return {"items": items}


@router.post("/ack")
async def ack(payload: Ack, db: AsyncSession = Depends(get_db)):
    if payload.outcome not in {"sent", "retry", "blocked"}:
        raise HTTPException(422, "Unknown delivery outcome")
    # Match scheduler/options lock order before locking any delivery or rule row.
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.id == payload.delivery_id, TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "reminder").with_for_update())).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Delivery not found")
    if row.data.get("token") != payload.token:
        raise HTTPException(409, "Delivery lease changed")
    if row.status in {"sent", "cancelled"}:
        return {"ok": True, "status": row.status}
    if row.status != "leased":
        raise HTTPException(409, "Delivery is not leased")
    if payload.outcome == "sent":
        row.status = "sent"
        row.data = {**row.data, "sent_at": now().isoformat()}
    elif payload.outcome == "retry":
        row.status = "pending"
        delay = min(3600, 30*2**min(row.data.get("attempts", 1), 7))
        row.data = {**row.data, "retry_at": (now()+timedelta(seconds=delay)).isoformat()}
    else:
        row.status = "cancelled"
        rule = await options_for(db, payload.telegram_user_id)
        if rule:
            rule.data = {**rule.data, "morning": None, "evening": None, "weekly": None,
                        "inactivity_days": None, "course": False, "next": {}}
        legacy = await db.get(TelegramAIReminderSettings, payload.telegram_user_id)
        if legacy:
            legacy.daily_time = None
            legacy.next_at = None
        pending = list((await db.execute(select(TelegramAIJournal).where(
            TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
            TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"])
        ))).scalars())
        for item in pending:
            item.status = "cancelled"
    await db.commit()
    return {"ok": True, "status": row.status}
