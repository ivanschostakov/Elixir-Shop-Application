import hashlib
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.profile import ensure_version
from src.app.modules.telegram_ai.journal import dump, now
from .common import KINDS_SECTION, router
from .helpers import course_dates, lock, owned, require_section
from .schemas import Course, CourseAction, CourseEvents, MODELS, RecordAction, RecordDraft, RecordRead


@router.post("/course/events")
async def course_events(payload: CourseEvents, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await owned(db, payload.telegram_user_id, payload.entry_id, "course")
    query = select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "course_event", TelegramAIJournal.data["course_id"].as_integer() == payload.entry_id)
    if payload.pending_only: query = query.where(TelegramAIJournal.status == "pending", TelegramAIJournal.occurred_at <= now())
    rows = list((await db.execute(query.order_by(TelegramAIJournal.occurred_at, TelegramAIJournal.id).offset(payload.offset).limit(payload.limit+1))).scalars())
    return {"items": [dump(row) for row in rows[:payload.limit]], "has_more": len(rows) > payload.limit}


@router.post("/record")
async def read_record(payload: RecordRead, db: AsyncSession = Depends(get_db)):
    row = await owned(db, payload.telegram_user_id, payload.entry_id)
    section = "food" if row.kind == "meal" else KINDS_SECTION.get(row.kind)
    if section is None: raise HTTPException(422, "Этот тип записи нельзя открыть здесь")
    require_section(section)
    return {"entry":dump(row)}


@router.post("/draft")
async def record_draft(payload: RecordDraft, db: AsyncSession = Depends(get_db)):
    require_section(KINDS_SECTION[payload.kind])
    await lock(db, payload.telegram_user_id)
    await ensure_version(db, payload.telegram_user_id, payload.expected_version)
    key = "record:"+hashlib.sha256(payload.request_key.encode()).hexdigest()
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row:
        if row.kind != payload.kind or row.data != payload.data: raise HTTPException(409, "Этот запрос уже использован")
        return {"ok": True, "entry": dump(row)}
    if payload.replaces_id:
        old = await owned(db, payload.telegram_user_id, payload.replaces_id, payload.kind)
        if old.status != "draft": raise HTTPException(409, "Черновик уже обработан")
        old.status = "replaced"
    row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=key, kind=payload.kind, status="draft", occurred_at=now(), data=payload.data)
    db.add(row)
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/action")
async def record_action(payload: RecordAction, db: AsyncSession = Depends(get_db)):
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id)
    if row.kind not in MODELS: raise HTTPException(422, "Неподдерживаемый тип записи")
    require_section(KINDS_SECTION[row.kind])
    target = {"confirm": "confirmed", "cancel": "cancelled", "stop": "stopped"}[payload.action]
    if row.status == target: return {"ok": True, "entry": dump(row)}
    if payload.action == "stop":
        if row.kind != "course" or row.status != "confirmed": raise HTTPException(409, "Остановить можно только активное расписание")
        events = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "course_event", TelegramAIJournal.status == "pending", TelegramAIJournal.occurred_at >= now()))).scalars())
        for event in events:
            if event.data.get("course_id") == row.id: event.status = "cancelled"
    elif row.status != "draft": raise HTTPException(409, "Черновик уже обработан")
    elif target == "confirmed":
        if row.kind == "workout" and row.data.get("active_entry_id"):
            active = await owned(db, payload.telegram_user_id, row.data["active_entry_id"], "workout")
            if active.status != "active": raise HTTPException(409, "Эта тренировка уже завершена. Обновите запись перед сохранением")
            active.status = "replaced"
        if row.kind in {"target", "program"}:
            previous = list((await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == row.kind, TelegramAIJournal.status == "confirmed"))).scalars())
            for old in previous: old.status = "replaced"
        if row.kind == "course":
            for instant in course_dates(Course.model_validate(row.data)): db.add(TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=f"course:{row.id}:{instant.isoformat()}", kind="course_event", status="pending", occurred_at=instant, data={"course_id": row.id, "name": row.data["name"], "dose_text": row.data["dose_text"]}))
    row.status = target
    await db.commit()
    return {"ok": True, "entry": dump(row)}


@router.post("/course/action")
async def course_action(payload: CourseAction, db: AsyncSession = Depends(get_db)):
    require_section("course")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "course_event")
    if row.status not in {"pending", payload.action}: raise HTTPException(409, "Отметка уже обработана")
    if row.occurred_at > now(): raise HTTPException(422, "Будущий приём нельзя отметить заранее")
    if row.status != payload.action:
        row.status = payload.action
        row.data = {**row.data, "completed_at": now().isoformat()}
    await db.commit()
    return {"ok": True, "entry": dump(row)}
