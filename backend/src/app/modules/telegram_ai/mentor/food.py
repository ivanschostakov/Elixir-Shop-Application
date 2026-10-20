import hashlib
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal
from src.app.modules.telegram_ai.profile import ensure_version
from src.app.modules.telegram_ai.journal import MealData, MealDraft, draft, dump, now
from .common import router
from .helpers import lock, owned, require_section
from .schemas import EstimateRecord, Favorite, MealLibrary, RepeatMeal


@router.post("/meals")
async def meals(payload: MealLibrary, db: AsyncSession = Depends(get_db)):
    require_section("food")
    query = select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.kind == "meal", TelegramAIJournal.status == "confirmed")
    if payload.query: query = query.where(TelegramAIJournal.data["name"].as_string().icontains(payload.query, autoescape=True))
    if payload.favorites_only: query = query.where(TelegramAIJournal.data["favorite"].as_boolean().is_(True))
    rows = list((await db.execute(query.order_by(TelegramAIJournal.occurred_at.desc(), TelegramAIJournal.id.desc()).offset(payload.offset).limit(11))).scalars())
    return {"items": [dump(r) for r in rows[:10]], "has_more": len(rows) > 10}


@router.post("/food/estimate")
async def estimate_food(payload: MealDraft, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    await ensure_version(db, payload.telegram_user_id, payload.expected_version)
    key = "food-estimate:" + hashlib.sha256(payload.request_key.encode()).hexdigest()
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=key, kind="food_estimate", status="preview", occurred_at=now(), data=payload.meal.model_dump())
        db.add(row)
        await db.commit()
    return {"ok": True, "estimate": dump(row), "recorded": False}


@router.post("/food/record")
async def record_estimate(payload: EstimateRecord, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    estimate = await owned(db, payload.telegram_user_id, payload.entry_id, "food_estimate")
    key = f"food-estimate-record:{estimate.id}"
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == key))).scalar_one_or_none()
    if row is None:
        meal = MealData.model_validate({k: estimate.data[k] for k in MealData.model_fields if k in estimate.data})
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key=key, kind="meal", status="confirmed", occurred_at=now(), data=meal.model_dump())
        db.add(row)
        estimate.status = "recorded"
        await db.commit()
    elif row.status != "confirmed": raise HTTPException(409, "Эта запись уже удалена. Для новой записи повторите поиск продукта.")
    return {"ok": True, "entry": dump(row)}


@router.post("/meals/delete")
async def delete_meal(payload: EstimateRecord, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "meal")
    if row.status == "deleted": return {"ok": True}
    if row.status != "confirmed": raise HTTPException(409, "Удалить из дневника можно только сохранённую еду.")
    row.status = "deleted"
    await db.commit()
    return {"ok": True}


@router.post("/meals/favorite")
async def favorite(payload: Favorite, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "meal")
    if row.status != "confirmed": raise HTTPException(409, "Сначала подтвердите еду")
    row.data = {**row.data, "favorite": payload.enabled}
    await db.commit()
    return {"ok": True}


@router.post("/meals/repeat")
async def repeat(payload: RepeatMeal, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = await owned(db, payload.telegram_user_id, payload.entry_id, "meal")
    if row.status != "confirmed": raise HTTPException(409, "Можно повторить только записанную еду")
    meal = MealData.model_validate({k: row.data[k] for k in MealData.model_fields if k in row.data})
    return await draft(MealDraft(telegram_user_id=payload.telegram_user_id, request_key=payload.request_key, meal=meal), db)


def remaining(target, totals):
    # Only explicitly confirmed user/specialist targets are accepted here.
    if not target or target.get("source") not in {"user", "specialist"}: return None
    return {k: round(max(0, target[k]-totals.get(k, 0)), 1) for k in ("kcal", "protein", "fat", "carbs") if target.get(k) is not None}
