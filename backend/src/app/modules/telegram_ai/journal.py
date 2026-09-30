"""Private Telegram mentor read models, meal drafts and opt-in reminders."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal, TelegramAIReminderSettings
from src.app.services.ai.companion.schemas import StrictModel
from .profile import Identity, snapshot

router = APIRouter()


def now():
    return datetime.now(timezone.utc)


class MealData(StrictModel):
    name: str = Field(min_length=1, max_length=240)
    kcal: float = Field(ge=0, le=10000)
    protein: float = Field(ge=0, le=2000)
    fat: float = Field(ge=0, le=2000)
    carbs: float = Field(ge=0, le=2000)
    note: str = Field(default="", max_length=1000)


class MealDraft(Identity):
    request_key: str = Field(min_length=8, max_length=128)
    meal: MealData
    replaces_id: int | None = Field(default=None, gt=0)
    occurred_at: datetime | None = None

    @field_validator("occurred_at")
    @classmethod
    def valid_time(cls, value):
        if value is not None and (value.tzinfo is None or not now()-timedelta(days=30) <= value <= now()+timedelta(minutes=5)):
            raise ValueError("Meal time must be recent and timezone aware")
        return value


class MealAction(Identity):
    entry_id: int = Field(gt=0)
    action: Literal["confirm", "cancel"]


class ReminderUpdate(Identity):
    timezone: str = Field(default="Europe/Moscow", max_length=80)
    daily_time: str | None = None

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc: raise ValueError("Unknown timezone") from exc
        return value

    @field_validator("daily_time")
    @classmethod
    def valid_clock(cls, value):
        if value is not None:
            try:
                parsed = time.fromisoformat(value)
                if len(value) != 5 or parsed.tzinfo is not None: raise ValueError()
            except ValueError as exc: raise ValueError("Expected HH:MM") from exc
        return value


def next_reminder(zone, clock, instant):
    local = instant.astimezone(ZoneInfo(zone))
    target = datetime.combine(local.date(), time.fromisoformat(clock), ZoneInfo(zone))
    if target <= local: target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def dump(row):
    return {"id": row.id, "kind": row.kind, "status": row.status,
            "occurred_at": row.occurred_at.isoformat(), **row.data}


async def settings_for(db, uid):
    row = await db.get(TelegramAIReminderSettings, uid)
    from .reminders import options_for
    options = await options_for(db, uid)
    return {"timezone": row.timezone if row else "Europe/Moscow", "daily_time": row.daily_time if row else None,
            "reminders": {k: v for k, v in options.data.items() if k not in {"next", "course_since"}} if options else {}}


@router.post("/dashboard")
async def dashboard(payload: Identity, db: AsyncSession = Depends(get_db)):
    saved = await snapshot(db, payload.telegram_user_id)
    settings = await settings_for(db, payload.telegram_user_id)
    instant = now(); zone = ZoneInfo(settings["timezone"])
    local = instant.astimezone(zone)
    start = datetime.combine(local.date(), time.min, zone)
    end = datetime.combine(local.date()+timedelta(days=1), time.min, zone)
    meals = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "meal", TelegramAIJournal.status == "confirmed",
        TelegramAIJournal.occurred_at >= start, TelegramAIJournal.occurred_at < end
    ).order_by(TelegramAIJournal.occurred_at))).scalars())
    weights = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "weight", TelegramAIJournal.status == "confirmed"
    ).order_by(TelegramAIJournal.occurred_at.desc(), TelegramAIJournal.id.desc()).limit(30))).scalars())
    pending = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "meal", TelegramAIJournal.status == "draft",
        TelegramAIJournal.created_at >= instant-timedelta(days=1)
    ).order_by(TelegramAIJournal.id.desc()).limit(1))).scalar_one_or_none()
    totals = {key: round(sum(float(m.data.get(key,0)) for m in meals),1) for key in ("kcal","protein","fat","carbs")}
    from .mentor import workspace_state
    workspace = await workspace_state(db, payload.telegram_user_id, totals)
    favorites = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "meal", TelegramAIJournal.status == "confirmed",
        TelegramAIJournal.data["favorite"].as_boolean().is_(True)
    ).order_by(TelegramAIJournal.occurred_at.desc()).limit(10))).scalars())
    workspace["favorite_meals"] = [dump(m) for m in favorites]
    first_weight = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "weight", TelegramAIJournal.status == "confirmed",
        TelegramAIJournal.occurred_at <= instant
    ).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id).limit(1))).scalar_one_or_none()
    target_weight = saved["profile"].get("target_weight_kg")
    current_weight = saved["profile"].get("current_weight_kg")
    if first_weight and target_weight is not None and current_weight is not None:
        initial = first_weight.data["weight_kg"]
        denominator = initial-target_weight
        workspace["goal_progress"] = {"initial_weight": initial, "since": first_weight.occurred_at.isoformat(),
            "percent": round(max(0, min(100, (initial-current_weight)/denominator*100)), 1) if denominator else None}
    return {**saved, "workspace": workspace, "settings": settings, "date": local.date().isoformat(), "now": instant.isoformat(),
        "meals": [dump(m) for m in meals], "totals": totals,
        "weights": [dump(w) for w in reversed(weights)], "draft": dump(pending) if pending else None}


@router.post("/journal/draft")
async def draft(payload: MealDraft, db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -payload.telegram_user_id})
    key = "meal:" + hashlib.sha256(payload.request_key.encode()).hexdigest()
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id==payload.telegram_user_id,
        TelegramAIJournal.request_key==key))).scalar_one_or_none()
    if row:
        return {"ok": True, "entry": dump(row)}
    if payload.replaces_id:
        old = await db.get(TelegramAIJournal,payload.replaces_id)
        if old is None or old.telegram_user_id != payload.telegram_user_id:
            raise HTTPException(404,"Запись не найдена")
        if old.status != "draft" and (row is None or old.id != row.id):
            raise HTTPException(409,"Эта оценка уже обработана")
        if row is None or old.id != row.id: old.status="replaced"
    if row is None:
        row=TelegramAIJournal(telegram_user_id=payload.telegram_user_id,request_key=key,
            kind="meal",status="draft",occurred_at=payload.occurred_at or now(),data={})
        db.add(row)
    row.data=payload.meal.model_dump()
    if payload.occurred_at: row.occurred_at=payload.occurred_at
    await db.commit()
    return {"ok":True,"entry":dump(row)}


@router.post("/journal/action")
async def meal_action(payload: MealAction, db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -payload.telegram_user_id})
    row=(await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.id==payload.entry_id,
        TelegramAIJournal.telegram_user_id==payload.telegram_user_id,TelegramAIJournal.kind=="meal").with_for_update())).scalar_one_or_none()
    if row is None: raise HTTPException(404,"Запись не найдена")
    target="confirmed" if payload.action=="confirm" else "cancelled"
    if row.status not in {"draft",target}: raise HTTPException(409,"Эта оценка уже обработана")
    row.status=target
    await db.commit()
    return {"ok":True,"entry":dump(row)}


@router.post("/reminder/settings")
async def reminder_settings(payload: ReminderUpdate, db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    from .reminders import Options, options, options_for
    existing = await options_for(db, payload.telegram_user_id)
    if existing:
        values = {k: v for k, v in existing.data.items() if k in Options.model_fields}
        values.update(telegram_user_id=payload.telegram_user_id, timezone=payload.timezone, evening=payload.daily_time)
        await options(Options.model_validate(values), db)
        return {"ok": True, **await settings_for(db, payload.telegram_user_id)}
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -payload.telegram_user_id})
    row=await db.get(TelegramAIReminderSettings,payload.telegram_user_id)
    if row is None:
        row=TelegramAIReminderSettings(telegram_user_id=payload.telegram_user_id)
        db.add(row)
    row.timezone=payload.timezone;row.daily_time=payload.daily_time
    row.next_at=next_reminder(row.timezone,row.daily_time,now()) if row.daily_time else None
    if not row.daily_time:
        queued = list((await db.execute(select(TelegramAIJournal).where(
            TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
            TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"])
        ))).scalars())
        for item in queued:
            if item.data.get("legacy"): item.status = "cancelled"
    await db.commit()
    return {"ok":True,**await settings_for(db,payload.telegram_user_id)}


@router.post("/reminder/due")
async def due(db: AsyncSession = Depends(get_db)):
    from .reminders import claim_due
    return await claim_due(db)
