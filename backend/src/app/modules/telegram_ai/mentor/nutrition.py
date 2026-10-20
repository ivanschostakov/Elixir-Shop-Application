from decimal import Decimal
from fastapi import Depends
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.database.models import TelegramAIJournal, TelegramAIProfile, TelegramAIReminderSettings
from src.app.modules.telegram_ai.profile import ProfilePatch, snapshot
from src.app.modules.telegram_ai.journal import now
from .common import router
from .helpers import lock, require_section
from .schemas import EraseData, NutritionEligibility, NutritionPreview


@router.post("/nutrition/eligibility")
async def nutrition_eligibility(payload: NutritionEligibility, db: AsyncSession = Depends(get_db)):
    require_section("food")
    await lock(db, payload.telegram_user_id)
    row = (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id == payload.telegram_user_id, TelegramAIJournal.request_key == "nutrition-eligibility"))).scalar_one_or_none()
    if row is None:
        row = TelegramAIJournal(telegram_user_id=payload.telegram_user_id, request_key="nutrition-eligibility", kind="nutrition_guard", status="confirmed", occurred_at=now(), data={})
        db.add(row)
    row.data = {"confirmed": payload.confirmed}
    row.occurred_at = now()
    await db.commit()
    return {"ok": True}


@router.post("/privacy/erase")
async def erase_data(payload: EraseData, db: AsyncSession = Depends(get_db)):
    # Same lock order as the reminder scheduler: no new lease during deletion.
    await db.execute(text("SELECT pg_advisory_xact_lock(733000111)"))
    await lock(db, payload.telegram_user_id)
    for model in (TelegramAIJournal, TelegramAIReminderSettings): await db.execute(delete(model).where(model.telegram_user_id == payload.telegram_user_id))
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
    if activity not in {"low", "light", "moderate", "high"}: missing.append("activity")
    if missing: return {"available": False, "missing": missing, "reason": "Дозаполните профиль для расчёта КБЖУ."}
    if saved["age"] < 18: return {"available": False, "reason": "Авторасчёт доступен только совершеннолетним. Нужны индивидуальные рекомендации специалиста."}
    profile = ProfileData(**{k: saved[k] for k in fields if saved.get(k) is not None}, activity=activity)
    return calculate_nutrition(profile, Decimal(str(saved["current_weight_kg"])), AI_COMPANION_NUTRITION_RULES_JSON, eligibility_confirmed=payload.eligibility_confirmed)
