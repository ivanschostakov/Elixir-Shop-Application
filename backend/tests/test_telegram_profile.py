import asyncio
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.app.modules.telegram_ai.profile import Identity, Update, context, update


def payload():
    return Update(telegram_user_id=88000000101, expected_version=0, request_key="telegram-message-1",
                  source_text="Мне 19, рост 183, вес 110, хочу 90 кг", evidence="Мне 19, рост 183, вес 110, хочу 90 кг",
                  patch={"age": 19, "height_cm": 183, "current_weight_kg": 110, "target_weight_kg": 90})


def test_rejects_invented_numbers_and_foreign_fields():
    valid = payload().model_dump()
    for changes in ({"patch": {"age": 20}}, {"evidence": "Мне 19 лет"}, {"patch": {"adult_confirmed": True}}, {"patch": {}}):
        with pytest.raises(ValidationError):
            Update.model_validate({**valid, **changes})
    assert payload().patch.current_weight_kg == 110


def test_profiles_durable_isolated_idempotent_and_versioned():
    from test_ai_companion_db import database, URL
    if not URL:
        pytest.skip("Needs isolated companion_test DB")
    async def run():
        async with database() as (db, user):
            first = await update(payload(), db)
            assert first["version"] == 1
            assert await update(payload(), db) == first
            assert (await context(Identity(telegram_user_id=88000000102), db))["profile"] == {}
            assert (await context(Identity(telegram_user_id=88000000101), db)) == {"version": 1, "profile": first["profile"]}
            correction = payload().model_dump()
            correction.update(expected_version=1, request_key="telegram-message-2", source_text="Теперь вес 109", evidence="вес 109", patch={"current_weight_kg": 109})
            second = await update(Update.model_validate(correction), db)
            assert second["profile"]["current_weight_kg"] == 109
            assert second["profile"]["target_weight_kg"] == 90
            correction.update(request_key="telegram-message-3")
            with pytest.raises(HTTPException) as e:
                await update(Update.model_validate(correction), db)
            assert e.value.status_code == 409
    asyncio.run(run())


def test_imports_only_confirmed_legacy_profile():
    from test_ai_companion_db import database, URL
    from src.database.models.ai.companion import AICompanionProfile, AICompanionEntry
    from datetime import datetime, timezone
    if not URL:
        pytest.skip("Needs isolated companion_test DB")
    async def run():
        async with database() as (db, user):
            user.telegram_user_id = 88000000103
            db.add(AICompanionProfile(user_id=user.id, data={"age": 19, "height_cm": "183", "target_weight_kg": "90", "goal": "weight_loss"}, settings={}))
            db.add(AICompanionEntry(user_id=user.id, kind="weight", occurred_at=datetime.now(timezone.utc), data={"weight_kg": "110"}))
            await db.flush()
            imported = await context(Identity(telegram_user_id=user.telegram_user_id), db)
            assert imported["profile"] == {"age": 19, "height_cm": 183, "target_weight_kg": 90, "goal": "weight_loss", "current_weight_kg": 110}
            assert imported["version"] == 0
    asyncio.run(run())
