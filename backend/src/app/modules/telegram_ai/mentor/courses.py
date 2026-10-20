import hashlib
from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.journal import dump, now
from .common import router
from .helpers import lock, owned, require_section
from .schemas import CourseReminder, CourseSupply, SupplyPreview


@router.post("/course/supply-preview")
async def supply_preview(payload: SupplyPreview):
    require_section("course")
    from src.app.modules.telegram_ai.course_inventory import normalize_supply
    try: data = normalize_supply(payload.model_dump())
    except ValueError as error: raise HTTPException(422, str(error)) from error
    return {"supply": {key: data[key] for key in ("supply_amount", "amount_per_intake", "supply_unit")}}


@router.post("/course/supply")
async def course_supply(payload: CourseSupply, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "course")
    if row.status != "confirmed": raise HTTPException(409, "Расписание не активно. Откройте актуальный курс.")
    key = hashlib.sha256(payload.request_key.encode()).hexdigest()
    receipts = row.data.get("supply_receipts", [])
    if key not in receipts:
        done_ids = list((await db.execute(select(TelegramAIJournal.id).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "course_event", TelegramAIJournal.status == "done", TelegramAIJournal.data["course_id"].as_integer() == row.id))).scalars())
        row.data = {**row.data, "supply_amount": payload.supply_amount,
            "amount_per_intake": payload.amount_per_intake, "supply_unit": payload.supply_unit,
            "package_count": None, "package_amount": None, "package_unit": None, "intake_unit": None,
            "supply_measured_at": now().isoformat(), "supply_baseline_done": done_ids,
            "supply_receipts": [*receipts, key][-100:]}
        await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/course/reminder")
async def course_reminder(payload: CourseReminder, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    course = await owned(db, payload.telegram_user_id, payload.entry_id, "course")
    if course.status != "confirmed": raise HTTPException(409, "Курс не активен")
    if course.data.get("reminder_time") != payload.reminder_time:
        course.data = {**course.data, "reminder_time": payload.reminder_time,
                       "reminder_revision": course.data.get("reminder_revision", 0)+1}
        events = list((await db.execute(select(TelegramAIJournal.id).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "course_event", TelegramAIJournal.data["course_id"].as_integer() == course.id))).scalars())
        if events:
            queued = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "reminder", TelegramAIJournal.status.in_(["pending", "leased"]), TelegramAIJournal.data["event_id"].as_integer().in_(events)))).scalars())
            for item in queued: item.status = "cancelled"
    await db.commit()
    return {"ok": True, "entry": dump(course)}
