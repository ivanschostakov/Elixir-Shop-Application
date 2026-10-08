"""Telegram-owned mentor workflows. All records stay in the existing journal."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import os
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator, model_validator
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.services.ai.companion.schemas import StrictModel
from src.database import get_db
from src.database.models import TelegramAIJournal, TelegramAIProfile, TelegramAIReminderSettings
from .profile import Identity, ProfilePatch, snapshot, ensure_version
from .journal import MealData, MealDraft, draft, dump, now, settings_for

router = APIRouter(prefix="/workspace")
SECTIONS = {"today", "food", "workouts", "course", "progress", "ask", "profile", "settings"}


def section_enabled(section):
    closed = {x.strip() for x in os.getenv("TELEGRAM_MENTOR_CLOSED_SECTIONS", "").split(",")}
    return section not in closed


def require_section(section):
    if not section_enabled(section):
        raise HTTPException(403, "Раздел временно отключён")


class NutritionPreview(Identity):
    eligibility_confirmed: bool = False
    activity: Literal["low", "light", "moderate", "high"] | None = None


class NutritionEligibility(Identity):
    confirmed: bool


@router.post("/nutrition/eligibility")
async def nutrition_eligibility(payload: NutritionEligibility, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.request_key == "nutrition-eligibility"))).scalar_one_or_none()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id,
            request_key="nutrition-eligibility", kind="nutrition_guard", status="confirmed", occurred_at=now(), data={})
        db.add(row)
    row.data = {"confirmed": payload.confirmed}
    row.occurred_at = now()
    await db.commit()
    return {"ok": True}


class EraseData(Identity):
    confirmed: Literal[True]


@router.post("/privacy/erase")
async def erase_data(payload: EraseData, db: AsyncSession = Depends(get_db)):
    # Same lock order as the reminder scheduler: no new lease during deletion.
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    for model in (TelegramAIJournal, TelegramAIReminderSettings):
        await db.execute(delete(model).where(model.telegram_user_id == payload.telegram_user_id))
    row = await db.get(TelegramAIProfile, payload.telegram_user_id, populate_existing=True)
    if row is None:
        row = TelegramAIProfile(telegram_user_id=payload.telegram_user_id, version=0, data={}, receipts=[])
        db.add(row)
    # Explicit nulls prevent re-importing app health data through legacy_profile.
    row.data = {field: None for field in ProfilePatch.model_fields}
    row.version += 1
    row.receipts = []
    await db.commit()
    return {"ok": True, "scope": "telegram_mentor"}


@router.post("/workout/discard-empty")
async def discard_empty_workout(payload: Identity, db: AsyncSession = Depends(get_db)):
    await lock(db, payload.telegram_user_id)
    rows = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "workout", TelegramAIJournal.status == "active"))).scalars()
    count = 0
    for row in rows:
        if not row.data.get("sets"):
            row.status = "cancelled"
            count += 1
    await db.commit()
    return {"ok": True, "discarded": count}


@router.post("/nutrition/preview")
async def nutrition_preview(payload: NutritionPreview, db: AsyncSession = Depends(get_db)):
    from config.companion import AI_COMPANION_NUTRITION_RULES_JSON
    from src.app.services.ai.companion.nutrition import calculate_nutrition
    from src.app.services.ai.companion.schemas import ProfileData
    require_section("food")
    saved = (await snapshot(db, payload.telegram_user_id))["profile"]
    fields = ("goal", "age", "sex", "height_cm", "target_weight_kg")
    activity = payload.activity or saved.get("activity")
    missing = [k for k in (*fields[:4], "current_weight_kg") if saved.get(k) is None]
    if activity not in {"low", "light", "moderate", "high"}:
        missing.append("activity")
    if missing:
        return {"available": False, "missing": missing, "reason": "Дозаполните профиль для расчёта КБЖУ."}
    if saved["age"] < 18:
        return {"available": False, "reason": "Авторасчёт доступен только совершеннолетним. Нужны индивидуальные рекомендации специалиста."}
    profile = ProfileData(**{k: saved[k] for k in fields if saved.get(k) is not None}, activity=activity)
    return calculate_nutrition(profile, Decimal(str(saved["current_weight_kg"])), AI_COMPANION_NUTRITION_RULES_JSON,
                               eligibility_confirmed=payload.eligibility_confirmed)


class NutritionTarget(StrictModel):
    kcal: float = Field(gt=0, le=10000, allow_inf_nan=False)
    protein: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    fat: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    carbs: float | None = Field(default=None, ge=0, le=2000, allow_inf_nan=False)
    source: Literal["user", "specialist"] = "user"


class Exercise(StrictModel):
    weekday: int = Field(ge=0, le=6)
    name: str = Field(min_length=1, max_length=120)
    sets: int = Field(ge=1, le=30)
    reps: int = Field(ge=1, le=200)


class Program(StrictModel):
    exercises: list[Exercise] = Field(min_length=1, max_length=100)


class WorkoutSet(StrictModel):
    exercise: str = Field(min_length=1, max_length=120)
    weight_kg: float = Field(ge=0, le=1000, allow_inf_nan=False)
    reps: int = Field(ge=1, le=1000)


class Workout(StrictModel):
    sets: list[WorkoutSet] = Field(min_length=1, max_length=200)
    duration_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)
    active_entry_id: int | None = Field(default=None, gt=0)


class PhysicalActivity(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    duration_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)


class Course(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    source: Literal["user", "specialist"]
    dose_text: str = Field(min_length=1, max_length=240)
    timezone: str = Field(default="Europe/Moscow", max_length=80)
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    times: list[str] = Field(min_length=1, max_length=8)
    supply_amount: float | None = Field(default=None, ge=0, le=1000000, allow_inf_nan=False)
    amount_per_intake: float | None = Field(default=None, gt=0, le=1000000, allow_inf_nan=False)
    supply_unit: str | None = Field(default=None, min_length=1, max_length=40)

    @model_validator(mode="after")
    def schedule_valid(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        if not 0 <= (self.end_date-self.start_date).days <= 365:
            raise ValueError("Course must span at most 366 days")
        if len(set(self.weekdays)) != len(self.weekdays) or any(d not in range(7) for d in self.weekdays):
            raise ValueError("Weekdays must be unique, Monday=0 through Sunday=6")
        if bool(self.weekdays) == bool(self.interval_days):
            raise ValueError("Choose weekdays OR interval_days anchored to start_date")
        if len(set(self.times)) != len(self.times):
            raise ValueError("Duplicate course times")
        for value in self.times:
            parsed = time.fromisoformat(value)
            if len(value) != 5 or parsed.tzinfo is not None:
                raise ValueError("Expected HH:MM")
        supplied = [self.supply_amount, self.amount_per_intake, self.supply_unit]
        if any(x is not None for x in supplied) and not all(x is not None for x in supplied):
            raise ValueError("Supply requires amount, consumption per intake and the same unit")
        return self


class Measurement(StrictModel):
    waist_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    chest_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    hips_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    photo_file_id: str | None = Field(default=None, min_length=1, max_length=512)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def nonempty(self):
        if not any((self.waist_cm, self.chest_cm, self.hips_cm, self.photo_file_id)):
            raise ValueError("Measurement or private Telegram photo required")
        return self


class Wellbeing(StrictModel):
    score: int = Field(ge=1, le=5)
    energy_score: int | None = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=2000)


MODELS = {"target": NutritionTarget, "program": Program, "workout": Workout, "activity_log": PhysicalActivity,
          "course": Course, "measurement": Measurement, "wellbeing": Wellbeing}
KINDS_SECTION = {"target": "food", "program": "workouts", "workout": "workouts", "activity_log": "workouts",
                 "course": "course", "measurement": "progress", "wellbeing": "today"}


class RecordDraft(Identity):
    request_key: str = Field(min_length=8, max_length=128)
    expected_version: int | None = Field(default=None, ge=0)
    kind: Literal["target", "program", "workout", "activity_log", "course", "measurement", "wellbeing"]
    data: dict
    replaces_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def structured_data(self):
        self.data = MODELS[self.kind].model_validate(self.data).model_dump(mode="json")
        if self.kind == "workout" and self.data.get("active_entry_id") is None:
            self.data.pop("active_entry_id", None)
        return self


class RecordAction(Identity):
    entry_id: int = Field(gt=0)
    action: Literal["confirm", "cancel", "stop"]


class CourseAction(Identity):
    entry_id: int = Field(gt=0)
    action: Literal["done", "skipped"]


class MealLibrary(Identity):
    query: str = Field(default="", max_length=240)
    favorites_only: bool = False
    offset: int = Field(default=0, ge=0, le=100000)


class Favorite(Identity):
    entry_id: int = Field(gt=0)
    enabled: bool


class RepeatMeal(Identity):
    entry_id: int = Field(gt=0)
    request_key: str = Field(min_length=8, max_length=128)


class WorkoutStart(Identity):
    request_key: str = Field(min_length=8, max_length=128)


class SetInput(WorkoutStart):
    entry_id: int = Field(gt=0)
    exercise_set: WorkoutSet


class WorkoutFinish(Identity):
    entry_id: int = Field(gt=0)
    duration_minutes: float | None = Field(default=None, gt=0, le=1440, allow_inf_nan=False)


@router.post("/workout/start")
async def workout_start(payload: WorkoutStart, db: AsyncSession = Depends(get_db)):
    require_section("workouts")
    await lock(db, payload.telegram_user_id)
    key = "workout:"+hashlib.sha256(payload.request_key.encode()).hexdigest()
    previous = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if previous:
        return {"ok": True, "entry": dump(previous)}
    active = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "workout", TelegramAIJournal.status == "active"
    ).limit(1))).scalar_one_or_none()
    if active:
        return {"ok": True, "entry": dump(active)}
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row is None:
        program = (await db.execute(select(TelegramAIJournal).where(
            TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
            TelegramAIJournal.kind == "program", TelegramAIJournal.status == "confirmed"
        ).order_by(TelegramAIJournal.id.desc()).limit(1))).scalar_one_or_none()
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=key,
            kind="workout", status="active", occurred_at=now(), data={"sets": [], "set_receipts": {},
                "program_id": program.id if program else None,
                "program_exercises": program.data["exercises"] if program else []})
        db.add(row)
        await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/workout/set")
async def workout_set(payload: SetInput, db: AsyncSession = Depends(get_db)):
    require_section("workouts")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "workout")
    digest = hashlib.sha256(payload.request_key.encode()).hexdigest()
    receipts = row.data.get("set_receipts", {})
    if digest in receipts:
        if receipts[digest] != payload.exercise_set.model_dump():
            raise HTTPException(409, "Этот запрос уже использован для другого подхода")
        return {"ok": True, "entry": dump(row)}
    if row.status != "active" or len(row.data["sets"]) >= 200:
        raise HTTPException(409, "Тренировка завершена или достигнут лимит подходов")
    row.data = {**row.data, "sets": [*row.data["sets"], payload.exercise_set.model_dump()],
                "set_receipts": {**receipts, digest: payload.exercise_set.model_dump()}}
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/workout/finish")
async def workout_finish(payload: WorkoutFinish, db: AsyncSession = Depends(get_db)):
    require_section("workouts")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "workout")
    if row.status == "confirmed":
        return {"ok": True, "entry": dump(row)}
    if row.status != "active" or not row.data["sets"]:
        raise HTTPException(409, "Запишите хотя бы один подход")
    if payload.duration_minutes is None:
        raise HTTPException(422, "Укажите фактическую длительность тренировки в минутах")
    row.data = {**row.data, "duration_minutes": payload.duration_minutes}
    row.status = "confirmed"
    await db.commit()
    return {"ok": True, "entry": dump(row)}


async def lock(db, uid):
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": -uid})


@router.post("/touch")
async def touch(payload: Identity, db: AsyncSession = Depends(get_db)):
    """Record interaction time only, never raw chat or media identifiers."""
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.request_key == "last-interaction"))).scalar_one_or_none()
    instant = now()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key="last-interaction",
            kind="activity", status="confirmed", occurred_at=instant, data={})
        db.add(row)
    row.occurred_at = instant
    from .reminders import options_for
    rule = await options_for(db, payload.telegram_user_id)
    if rule and rule.data.get("inactivity_days"):
        rule.data = {**rule.data, "next": {**rule.data.get("next", {}),
            "inactivity": (instant+timedelta(days=rule.data["inactivity_days"])).isoformat()}}
    pending = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"])
    ))).scalars())
    for item in pending:
        if item.data.get("reminder_kind") == "inactivity": item.status = "cancelled"
    await db.commit()
    return {"ok": True}


async def owned(db, uid, entry_id, kind=None):
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.id == entry_id, TelegramAIJournal.telegram_user_id == uid
    ).with_for_update())).scalar_one_or_none()
    if row is None or (kind is not None and row.kind != kind):
        raise HTTPException(404, "Запись не найдена")
    return row


class RecordRead(Identity):
    entry_id: int = Field(gt=0)


@router.post("/record")
async def read_record(payload: RecordRead, db: AsyncSession = Depends(get_db)):
    row = await owned(db, payload.telegram_user_id, payload.entry_id)
    section = "food" if row.kind == "meal" else KINDS_SECTION.get(row.kind)
    if section is None: raise HTTPException(422, "Этот тип записи нельзя открыть здесь")
    require_section(section)
    return {"entry":dump(row)}


def course_dates(course):
    zone = ZoneInfo(course.timezone)
    day = course.start_date
    while day <= course.end_date:
        scheduled = ((day-course.start_date).days % course.interval_days == 0) if course.interval_days else day.weekday() in course.weekdays
        if scheduled:
            for clock in sorted(course.times):
                yield datetime.combine(day, time.fromisoformat(clock), zone).astimezone(timezone.utc)
        day += timedelta(days=1)


@router.post("/draft")
async def record_draft(payload: RecordDraft, db: AsyncSession = Depends(get_db)):
    require_section(KINDS_SECTION[payload.kind])
    await lock(db, payload.telegram_user_id)
    await ensure_version(db, payload.telegram_user_id, payload.expected_version)
    key = "record:"+hashlib.sha256(payload.request_key.encode()).hexdigest()
    row = (await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row:
        if row.kind != payload.kind or row.data != payload.data:
            raise HTTPException(409, "Этот запрос уже использован")
        return {"ok": True, "entry": dump(row)}
    if payload.replaces_id:
        old = await owned(db, payload.telegram_user_id, payload.replaces_id, payload.kind)
        if old.status != "draft":
            raise HTTPException(409, "Черновик уже обработан")
        old.status = "replaced"
    row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=key,
        kind=payload.kind, status="draft", occurred_at=now(), data=payload.data)
    db.add(row)
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/action")
async def record_action(payload: RecordAction, db: AsyncSession = Depends(get_db)):
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id)
    if row.kind not in MODELS:
        raise HTTPException(422, "Неподдерживаемый тип записи")
    require_section(KINDS_SECTION[row.kind])
    target = {"confirm": "confirmed", "cancel": "cancelled", "stop": "stopped"}[payload.action]
    if row.status == target:
        return {"ok": True, "entry": dump(row)}
    if payload.action == "stop":
        if row.kind != "course" or row.status != "confirmed":
            raise HTTPException(409, "Остановить можно только активное расписание")
        events = list((await db.execute(select(TelegramAIJournal).where(
            TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
            TelegramAIJournal.kind == "course_event", TelegramAIJournal.status == "pending",
            TelegramAIJournal.occurred_at >= now()))).scalars())
        for event in events:
            if event.data.get("course_id") == row.id:
                event.status = "cancelled"
    elif row.status != "draft":
        raise HTTPException(409, "Черновик уже обработан")
    elif target == "confirmed":
        if row.kind == "workout" and row.data.get("active_entry_id"):
            active = await owned(db, payload.telegram_user_id, row.data["active_entry_id"], "workout")
            if active.status != "active":
                raise HTTPException(409, "Эта тренировка уже завершена. Обновите запись перед сохранением")
            active.status = "replaced"
        if row.kind in {"target", "program"}:
            previous = list((await db.execute(select(TelegramAIJournal).where(
                TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
                TelegramAIJournal.kind == row.kind, TelegramAIJournal.status == "confirmed"))).scalars())
            for old in previous:
                old.status = "replaced"
        if row.kind == "course":
            for instant in course_dates(Course.model_validate(row.data)):
                db.add(TelegramAIJournal(telegram_user_id=payload.telegram_user_id,
                    request_key=f"course:{row.id}:{instant.isoformat()}", kind="course_event",
                    status="pending", occurred_at=instant,
                    data={"course_id": row.id, "name": row.data["name"], "dose_text": row.data["dose_text"]}))
    row.status = target
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/course/action")
async def course_action(payload: CourseAction, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "course_event")
    if row.status not in {"pending", payload.action}:
        raise HTTPException(409, "Отметка уже обработана")
    if row.occurred_at > now():
        raise HTTPException(422, "Будущий приём нельзя отметить заранее")
    row.status = payload.action
    await db.commit()
    return {"ok": True, "entry": dump(row)}


class CourseReminder(Identity):
    entry_id: int = Field(gt=0)
    reminder_time: str | None = None

    @field_validator("reminder_time")
    @classmethod
    def clock(cls, value):
        from .journal import ReminderUpdate
        return ReminderUpdate.valid_clock(value)


@router.post("/course/reminder")
async def course_reminder(payload: CourseReminder, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    course = await owned(db, payload.telegram_user_id, payload.entry_id, "course")
    if course.status != "confirmed":
        raise HTTPException(409, "Курс не активен")
    if course.data.get("reminder_time") != payload.reminder_time:
        course.data = {**course.data, "reminder_time": payload.reminder_time,
                       "reminder_revision": course.data.get("reminder_revision", 0)+1}
        events = list((await db.execute(select(TelegramAIJournal.id).where(
            TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
            TelegramAIJournal.kind == "course_event", TelegramAIJournal.data["course_id"].as_integer() == course.id))).scalars())
        if events:
            queued = list((await db.execute(select(TelegramAIJournal).where(
                TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
                TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"]),
                TelegramAIJournal.data["event_id"].as_integer().in_(events)))).scalars())
            for item in queued:
                item.status = "cancelled"
    await db.commit()
    return {"ok": True, "entry": dump(course)}


@router.post("/meals")
async def meals(payload: MealLibrary, db: AsyncSession = Depends(get_db)):
    require_section("food")
    query = select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind == "meal", TelegramAIJournal.status == "confirmed")
    if payload.query:
        query = query.where(TelegramAIJournal.data["name"].as_string().icontains(payload.query, autoescape=True))
    if payload.favorites_only:
        query = query.where(TelegramAIJournal.data["favorite"].as_boolean().is_(True))
    rows = list((await db.execute(query.order_by(TelegramAIJournal.occurred_at.desc(),
        TelegramAIJournal.id.desc()).offset(payload.offset).limit(11))).scalars())
    return {"items": [dump(r) for r in rows[:10]], "has_more": len(rows) > 10}


@router.post("/meals/favorite")
async def favorite(payload: Favorite, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "meal")
    if row.status != "confirmed":
        raise HTTPException(409, "Сначала подтвердите еду")
    row.data = {**row.data, "favorite": payload.enabled}
    await db.commit()
    return {"ok": True}


@router.post("/meals/repeat")
async def repeat(payload: RepeatMeal, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "meal")
    if row.status != "confirmed":
        raise HTTPException(409, "Можно повторить только записанную еду")
    meal = MealData.model_validate({k: row.data[k] for k in MealData.model_fields if k in row.data})
    return await draft(MealDraft(telegram_user_id=payload.telegram_user_id,
        request_key=payload.request_key, meal=meal), db)


def remaining(target, totals):
    # Only explicitly confirmed user/specialist targets are accepted here.
    if not target or target.get("source") not in {"user", "specialist"}:
        return None
    return {k: round(max(0, target[k]-totals.get(k, 0)), 1) for k in ("kcal", "protein", "fat", "carbs")
            if target.get(k) is not None}


def summarize(rows, instant, zone, days=7):
    local = instant.astimezone(zone)
    start = datetime.combine(local.date()-timedelta(days=days-1), time.min, zone)
    week = [r for r in rows if start <= r.occurred_at <= instant]
    confirmed = [r for r in week if r.status == "confirmed"]
    workouts = [r for r in confirmed if r.kind == "workout"]
    activities = [r for r in confirmed if r.kind == "activity_log"]
    weights = sorted([r for r in confirmed if r.kind == "weight"], key=lambda r: (r.occurred_at, r.id))
    events = [r for r in week if r.kind == "course_event" and r.status != "cancelled"]
    seven_start = datetime.combine(local.date()-timedelta(days=6), time.min, zone)
    seven_weights = [r.data["weight_kg"] for r in weights if r.occurred_at >= seven_start]
    wellbeing = [r.data["score"] for r in confirmed if r.kind == "wellbeing"]
    energy = [r.data["energy_score"] for r in confirmed if r.kind == "wellbeing" and r.data.get("energy_score") is not None]
    daily = {}
    for row in confirmed:
        if row.kind == "meal":
            day = row.occurred_at.astimezone(zone).date()
            value = daily.setdefault(day, {"kcal": 0, "protein": 0})
            for key in value:
                value[key] += row.data.get(key, 0)
    targets = sorted([r for r in rows if r.kind == "target" and r.status in {"confirmed", "replaced"}], key=lambda r: (r.occurred_at, r.id))
    protein_actual = protein_target = 0
    protein_days = 0
    for day, values in daily.items():
        target = next((r for r in reversed(targets) if r.occurred_at.astimezone(zone).date() <= day), None)
        if target and target.data.get("protein") and target.data.get("source") in {"user", "specialist"}:
            protein_actual += values["protein"]
            protein_target += target.data["protein"]
            protein_days += 1
    programs = sorted([r for r in rows if r.kind == "program" and r.status in {"confirmed", "replaced"}], key=lambda r: (r.occurred_at, r.id))
    planned = 0
    for n in range(days):
        day = start.date()+timedelta(days=n)
        program = next((r for r in reversed(programs) if r.occurred_at.astimezone(zone).date() <= day), None)
        if program and any(e["weekday"] == day.weekday() for e in program.data["exercises"]):
            planned += 1
    return {"days": days, "from": start.date().isoformat(), "to": local.date().isoformat(),
        "nutrition_days": len(daily), "average_kcal": round(sum(v["kcal"] for v in daily.values())/len(daily), 1) if daily else None,
        "protein_target_percent": round(100*protein_actual/protein_target, 1) if protein_target else None,
        "protein_target_days": protein_days, "planned_workouts": planned,
        "weight_measurements": len(weights), "weight_mean_7d": round(sum(seven_weights)/len(seven_weights), 2) if seven_weights else None,
        "weight_samples_7d": len(seven_weights), "wellbeing_mean": round(sum(wellbeing)/len(wellbeing), 2) if wellbeing else None,
        "wellbeing_samples": len(wellbeing), "energy_mean": round(sum(energy)/len(energy), 2) if energy else None,
        "energy_samples": len(energy), "meals": sum(r.kind == "meal" for r in confirmed),
        "workouts": len(workouts), "duration_minutes": round(sum(r.data["duration_minutes"] for r in workouts), 1),
        "activities": len(activities), "activity_duration_minutes": round(sum(r.data["duration_minutes"] for r in activities), 1),
        "volume_kg": round(sum(s["weight_kg"]*s["reps"] for r in workouts for s in r.data["sets"]), 1),
        "weight_change_kg": round(weights[-1].data["weight_kg"]-weights[0].data["weight_kg"], 2) if len(weights)>1 else None,
        "course_due": len(events), "course_done": sum(r.status == "done" for r in events),
        "nutrition": {k: round(sum(r.data.get(k, 0) for r in confirmed if r.kind == "meal"), 1)
                      for k in ("kcal", "protein", "fat", "carbs")}}


class Report(Identity):
    days: Literal[7, 30] = 7


@router.post("/report")
async def report(payload: Report, db: AsyncSession = Depends(get_db)):
    require_section("progress")
    settings = await settings_for(db, payload.telegram_user_id)
    instant = now()
    zone = ZoneInfo(settings["timezone"])
    start = datetime.combine(instant.astimezone(zone).date()-timedelta(days=payload.days-1), time.min, zone)
    rows = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == payload.telegram_user_id,
        TelegramAIJournal.kind.in_(["weight", "workout", "activity_log", "meal", "course_event", "wellbeing", "target", "program"]),
        (TelegramAIJournal.occurred_at >= start) | TelegramAIJournal.kind.in_(["target", "program"]),
        TelegramAIJournal.occurred_at <= instant
    ).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id))).scalars())
    return summarize(rows, instant, zone, payload.days)


async def workspace_state(db, uid, totals=None):
    settings = await settings_for(db, uid)
    instant = now()
    zone = ZoneInfo(settings["timezone"])
    # Query an explicit date window, never silently truncate weekly totals.
    rows = list((await db.execute(select(TelegramAIJournal).where(
        TelegramAIJournal.telegram_user_id == uid,
        TelegramAIJournal.kind.in_([*MODELS, "meal", "weight", "course_event"]),
        TelegramAIJournal.status.not_in(["draft", "cancelled"]),
        (TelegramAIJournal.status != "replaced") | TelegramAIJournal.kind.in_(["target", "program"]),
        (TelegramAIJournal.occurred_at >= instant-timedelta(days=31)) |
        TelegramAIJournal.kind.in_(["target", "program", "course"])
    ).order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id))).scalars())
    current = lambda kind: next((r for r in reversed(rows) if r.kind == kind and r.status == "confirmed"), None)
    target = current("target")
    program = current("program")
    today = [r for r in rows if r.occurred_at.astimezone(zone).date() == instant.astimezone(zone).date()]
    courses = []
    for course in (r for r in rows if r.kind == "course" and r.status == "confirmed"):
        events = list((await db.execute(select(TelegramAIJournal).where(
            TelegramAIJournal.telegram_user_id == uid, TelegramAIJournal.kind == "course_event",
            TelegramAIJournal.data["course_id"].as_integer() == course.id
        ).order_by(TelegramAIJournal.occurred_at))).scalars())
        done = sum(e.status == "done" for e in events)
        due_count = sum(e.occurred_at <= instant and e.status != "cancelled" for e in events)
        pending = [e for e in events if e.status == "pending" and e.occurred_at >= instant]
        supply = None
        amount = course.data.get("amount_per_intake")
        if amount is not None and course.data.get("supply_amount") is not None:
            left = max(0, course.data["supply_amount"]-done*amount)
            count = int(left//amount)
            supply = {"remaining": round(left, 4), "unit": course.data["supply_unit"],
                "intakes_available": count, "shortfall": round(max(0, len(pending)*amount-left), 4),
                "runs_out_at": pending[count].occurred_at.isoformat() if count < len(pending) else None}
        courses.append({**dump(course), "done": done, "due": due_count, "supply": supply,
            "calendar": [dump(e) for e in events if e.occurred_at >= instant-timedelta(days=7)][:40]})
    statuses = list((await db.execute(select(TelegramAIJournal.id, TelegramAIJournal.kind, TelegramAIJournal.status).where(
        TelegramAIJournal.telegram_user_id == uid,
        TelegramAIJournal.kind.in_([*MODELS, "meal"])
    ).order_by(TelegramAIJournal.id.desc()).limit(20))).mappings())
    return {"sections": {s: section_enabled(s) for s in sorted(SECTIONS)},
        "record_statuses": [dict(row) for row in statuses],
        "target": dump(target) if target else None, "remaining": remaining(target.data if target else None, totals or {}),
        "program": dump(program) if program else None,
        "today_exercises": [e for e in program.data["exercises"] if e["weekday"] == instant.astimezone(zone).weekday()] if program else [],
        "today_course": [dump(r) for r in today if r.kind == "course_event" and r.status != "cancelled"],
        "today_workouts": [dump(r) for r in today if r.kind == "workout" and r.status == "confirmed"],
        "today_activities": [dump(r) for r in today if r.kind == "activity_log" and r.status == "confirmed"],
        "recent_workouts": [dump(r) for r in rows if r.kind == "workout" and r.status == "confirmed"][-10:],
        "recent_activities": [dump(r) for r in rows if r.kind == "activity_log" and r.status == "confirmed"][-10:],
        "active_workout": next((dump(r) for r in reversed(rows) if r.kind == "workout" and r.status == "active"), None),
        "today_wellbeing": [dump(r) for r in today if r.kind == "wellbeing" and r.status == "confirmed"],
        "courses": courses, "weekly": summarize(rows, instant, zone),
        "measurements": [dump(r) for r in rows if r.kind == "measurement" and r.status == "confirmed"][-30:]}


@router.post("/state")
async def state(payload: Identity, db: AsyncSession = Depends(get_db)):
    return await workspace_state(db, payload.telegram_user_id)
