import hashlib
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.journal import dump, now
from .common import router
from .helpers import lock, owned, require_section
from .schemas import SetInput, WorkoutFinish, WorkoutStart


@router.post("/workout/start")
async def workout_start(payload: WorkoutStart, db: AsyncSession = Depends(get_db)):
    require_section("workouts")
    await lock(db, payload.telegram_user_id)
    key = "workout:"+hashlib.sha256(payload.request_key.encode()).hexdigest()
    previous = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if previous: return {"ok": True, "entry": dump(previous)}
    active = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "workout", TelegramAIJournal.status == "active").limit(1))).scalar_one_or_none()
    if active: return {"ok": True, "entry": dump(active)}
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row is None:
        program = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "program", TelegramAIJournal.status == "confirmed").order_by(TelegramAIJournal.id.desc()).limit(1))).scalar_one_or_none()
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
        if receipts[digest] != payload.exercise_set.model_dump(): raise HTTPException(409, "Этот запрос уже использован для другого подхода")
        return {"ok": True, "entry": dump(row)}
    if row.status != "active" or len(row.data["sets"]) >= 200: raise HTTPException(409, "Тренировка завершена или достигнут лимит подходов")
    row.data = {**row.data, "sets": [*row.data["sets"], payload.exercise_set.model_dump()],
                "set_receipts": {**receipts, digest: payload.exercise_set.model_dump()}}
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/workout/finish")
async def workout_finish(payload: WorkoutFinish, db: AsyncSession = Depends(get_db)):
    require_section("workouts")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "workout")
    if row.status == "confirmed": return {"ok": True, "entry": dump(row)}
    if row.status != "active" or not row.data["sets"]: raise HTTPException(409, "Запишите хотя бы один подход")
    if payload.duration_minutes is None: raise HTTPException(422, "Укажите фактическую длительность тренировки в минутах")
    row.data = {**row.data, "duration_minutes": payload.duration_minutes}
    row.status = "confirmed"
    await db.commit()
    return {"ok": True, "entry": dump(row)}
