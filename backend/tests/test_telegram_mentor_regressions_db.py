import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from test_ai_companion_db import URL, database, enable
from src.app.modules.telegram_ai import mentor as m, profile as p, journal as j
from src.database.models import TelegramAIJournal, TelegramAIProfile, TelegramAIReminderSettings, User
from src.database.models.ai.companion import AICompanionProfile

pytestmark = pytest.mark.skipif(not URL, reason="Requires disposable companion_test DB")
UID = 88000000887


def test_erasure_is_confirmed_owner_scoped_and_does_not_reimport_app_profile():
    with pytest.raises(ValidationError):
        m.EraseData(telegram_user_id=UID,confirmed=False)
    async def run():
        async with database() as (db,user):
            user.telegram_user_id = UID
            app_profile = await enable(db,user)
            app_profile.data = {"age":30,"height_cm":180,"goal":"maintain"}
            await db.commit()
            assert (await p.snapshot(db,UID))["profile"]["age"] == 30
            await p.update(p.Update(telegram_user_id=UID,expected_version=0,request_key="weight-test-own",source_text="Вес 80",evidence="Вес 80",patch={"current_weight_kg":80}),db)
            await p.update(p.Update(telegram_user_id=UID+1,expected_version=0,request_key="weight-test-other",source_text="Вес 70",evidence="Вес 70",patch={"current_weight_kg":70}),db)
            db.add(TelegramAIReminderSettings(telegram_user_id=UID,timezone="UTC",daily_time="19:00",next_at=j.now()))
            await db.commit()
            version=(await p.snapshot(db,UID))["version"]
            await m.erase_data(m.EraseData(telegram_user_id=UID,confirmed=True),db)
            assert (await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id==UID))).scalars().all() == []
            assert await db.get(TelegramAIReminderSettings,UID) is None
            saved=await p.snapshot(db,UID)
            assert saved["version"] == version+1
            assert all(v is None for v in saved["profile"].values())
            assert (await p.snapshot(db,UID+1))["profile"]["current_weight_kg"] == 70
            assert (await db.get(User,user.id)).telegram_user_id == UID
            assert (await db.get(AICompanionProfile,app_profile.id)).data["age"] == 30
            # Old profile writes cannot restore erased personal data.
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as error:
                await p.update(p.Update(telegram_user_id=UID,expected_version=version,request_key="late-weight-write",source_text="Вес 81",evidence="Вес 81",patch={"current_weight_kg":81}),db)
            assert error.value.status_code == 409
            with pytest.raises(HTTPException) as error:
                await m.record_draft(m.RecordDraft(telegram_user_id=UID,expected_version=version,request_key="late-target-draft",kind="target",data={"kcal":2000}),db)
            assert error.value.status_code == 409
            with pytest.raises(HTTPException) as error:
                await j.draft(j.MealDraft(telegram_user_id=UID,expected_version=version,request_key="late-meal-draft",meal={"name":"Late","kcal":100,"protein":1,"fat":2,"carbs":3}),db)
            assert error.value.status_code == 409
    asyncio.run(run())


def test_discard_empty_preserves_nonempty_and_other_users_workouts():
    async def run():
        async with database() as (db,_):
            empty=TelegramAIJournal(telegram_user_id=UID,request_key="empty-workout",kind="workout",status="active",occurred_at=j.now(),data={"sets":[]})
            nonempty=TelegramAIJournal(telegram_user_id=UID,request_key="real-workout",kind="workout",status="active",occurred_at=j.now(),data={"sets":[{"exercise":"Squat","weight_kg":30,"reps":10}]})
            other=TelegramAIJournal(telegram_user_id=UID+1,request_key="other-workout",kind="workout",status="active",occurred_at=j.now(),data={"sets":[]})
            db.add_all([empty,nonempty,other])
            await db.commit()
            assert (await m.discard_empty_workout(p.Identity(telegram_user_id=UID),db))["discarded"] == 1
            assert empty.status == "cancelled" and nonempty.status == other.status == "active"
            assert (await m.discard_empty_workout(p.Identity(telegram_user_id=UID),db))["discarded"] == 0
    asyncio.run(run())


def test_nutrition_eligibility_is_explicit_revocable_and_expires():
    async def run():
        async with database() as (db,_):
            identity=p.Identity(telegram_user_id=UID)
            assert not (await j.dashboard(identity,db))["workspace"]["nutrition_eligibility_confirmed"]
            await m.nutrition_eligibility(m.NutritionEligibility(telegram_user_id=UID,confirmed=True),db)
            assert (await j.dashboard(identity,db))["workspace"]["nutrition_eligibility_confirmed"]
            assert not (await j.dashboard(p.Identity(telegram_user_id=UID+1),db))["workspace"]["nutrition_eligibility_confirmed"]
            await m.nutrition_eligibility(m.NutritionEligibility(telegram_user_id=UID,confirmed=False),db)
            assert not (await j.dashboard(identity,db))["workspace"]["nutrition_eligibility_confirmed"]
            await m.nutrition_eligibility(m.NutritionEligibility(telegram_user_id=UID,confirmed=True),db)
            row=(await db.execute(select(TelegramAIJournal).where(TelegramAIJournal.telegram_user_id==UID,TelegramAIJournal.kind=="nutrition_guard"))).scalar_one()
            row.occurred_at=j.now()-timedelta(days=31)
            await db.commit()
            assert not (await j.dashboard(identity,db))["workspace"]["nutrition_eligibility_confirmed"]
    asyncio.run(run())
