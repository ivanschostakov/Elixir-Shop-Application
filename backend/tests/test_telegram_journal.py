import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from src.app.modules.telegram_ai.journal import (MealDraft,MealData,MealAction,ReminderUpdate,
    draft,meal_action,dashboard,reminder_settings,due,next_reminder)
from src.app.modules.telegram_ai.profile import Identity,Update,update
from test_ai_companion_db import database,URL

UID=88000000551
MEAL=MealData(name="Рис с курицей",kcal=450,protein=30,fat=10,carbs=60)


def test_settings_validation_and_timezone_schedule():
    for data in ({'daily_time':'99:99'},{'timezone':'bad/zone'},{'daily_time':'20:30:15'}):
        with pytest.raises(ValidationError): ReminderUpdate(telegram_user_id=UID,**data)
    moment=datetime(2030,1,1,17,30,tzinfo=timezone.utc)
    assert next_reminder('Europe/Moscow','21:00',moment)==datetime(2030,1,1,18,tzinfo=timezone.utc)
    assert next_reminder('Europe/Moscow','21:00',moment+timedelta(hours=1))==datetime(2030,1,2,18,tzinfo=timezone.utc)
    with pytest.raises(ValidationError): MealData(name='bad',kcal=-1,protein=0,fat=0,carbs=0)


@pytest.mark.skipif(not URL,reason='Isolated database required')
def test_meal_confirmation_retries_ownership_and_daily_totals():
    async def run():
        async with database() as (db,user):
            payload=MealDraft(telegram_user_id=UID,request_key='meal-message-1',meal=MEAL)
            row=(await draft(payload,db))['entry']
            assert (await draft(payload,db))['entry']['id']==row['id']
            assert (await dashboard(Identity(telegram_user_id=UID),db))['totals']['kcal']==0
            with pytest.raises(HTTPException) as error:
                await meal_action(MealAction(telegram_user_id=UID+1,entry_id=row['id'],action='confirm'),db)
            assert error.value.status_code==404
            action=MealAction(telegram_user_id=UID,entry_id=row['id'],action='confirm')
            await meal_action(action,db);await meal_action(action,db)
            summary=await dashboard(Identity(telegram_user_id=UID),db)
            assert len(summary['meals'])==1 and summary['totals']['kcal']==450
            assert (await dashboard(Identity(telegram_user_id=UID+1),db))['meals']==[]
            assert (await draft(payload,db))['entry']['status']=='confirmed'
    asyncio.run(run())


@pytest.mark.skipif(not URL,reason='Isolated database required')
def test_correction_replaces_old_draft_and_weight_history_is_not_duplicated():
    async def run():
        async with database() as (db,user):
            old=(await draft(MealDraft(telegram_user_id=UID,request_key='meal-old-1',meal=MEAL),db))['entry']
            changed=MEAL.model_copy(update={'kcal':400})
            new_payload=MealDraft(telegram_user_id=UID,request_key='meal-new-2',meal=changed,replaces_id=old['id'])
            new=(await draft(new_payload,db))['entry']
            assert (await draft(new_payload,db))['entry']['id']==new['id']
            with pytest.raises(HTTPException) as error:
                await meal_action(MealAction(telegram_user_id=UID,entry_id=old['id'],action='confirm'),db)
            assert error.value.status_code==409
            await meal_action(MealAction(telegram_user_id=UID,entry_id=new['id'],action='confirm'),db)
            payload=Update(telegram_user_id=UID,expected_version=0,request_key='weight-message-1',source_text='Вес 110',evidence='Вес 110',patch={'current_weight_kg':110})
            await update(payload,db);await update(payload,db)
            await update(Update(telegram_user_id=UID,expected_version=1,request_key='weight-message-2',source_text='109',evidence='109',patch={'current_weight_kg':109}),db)
            data=await dashboard(Identity(telegram_user_id=UID),db)
            assert [w['weight_kg'] for w in data['weights']]==[110,109]
            assert data['totals']['kcal']==400
    asyncio.run(run())


@pytest.mark.skipif(not URL,reason='Isolated database required')
def test_reminders_are_opt_in_leased_retried_and_acknowledged(monkeypatch):
    import src.app.modules.telegram_ai.reminders as module
    import src.app.modules.telegram_ai.journal as journal
    from src.app.modules.telegram_ai.reminders import ack, Ack
    instant=datetime(2030,1,1,17,59,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'now',lambda:instant)
    monkeypatch.setattr(journal,'now',lambda:instant)
    async def run():
        nonlocal instant
        async with database() as (db,user):
            assert (await due(db))['items']==[]
            await reminder_settings(ReminderUpdate(telegram_user_id=UID,timezone='Europe/Moscow',daily_time='21:00'),db)
            instant+=timedelta(minutes=2)
            delivery = (await due(db))['items'][0]
            assert delivery['telegram_user_id'] == UID
            assert (await due(db))['items']==[]
            instant+=timedelta(minutes=6)
            retry = (await due(db))['items'][0]
            assert retry['delivery_id'] == delivery['delivery_id'] and retry['token'] != delivery['token']
            await ack(Ack(telegram_user_id=UID, delivery_id=retry['delivery_id'], token=retry['token'], outcome='sent'), db)
            assert (await due(db))['items']==[]
            instant+=timedelta(days=1,hours=1)
            assert len((await due(db))['items']) == 1  # Outages no longer silently discard reminders.
            await reminder_settings(ReminderUpdate(telegram_user_id=UID,daily_time=None),db)
            instant+=timedelta(days=1)
            assert (await due(db))['items']==[]
    asyncio.run(run())
