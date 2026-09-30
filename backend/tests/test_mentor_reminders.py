import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

import config
from src.app.services.ai.companion import service
from src.database.models import AIChat, AIMessage
from src.database.models.ai.companion import AICompanionReminder
from src.integrations.ai.enums import MessageSender
from test_ai_companion_db import URL, database, enable

from src.app.services.ai.companion.jobs import inactivity_slot, last_user_activity, reminder_text, schedule_inactivity
from src.app.services.ai.companion.schemas import Settings


def test_inactivity_is_opt_in_and_waits_the_full_interval():
    now = datetime(2030, 1, 10, 12, tzinfo=timezone.utc)
    assert inactivity_slot(now - timedelta(days=9), Settings(), now) is None
    settings = Settings(inactivity_days=3, inactivity_time="18:00", timezone="Europe/Moscow")
    assert inactivity_slot(now - timedelta(days=2, hours=23), settings, now) is None
    key, due = inactivity_slot(now - timedelta(days=3), settings, now)
    assert key.startswith("inactivity:")
    assert due == now.replace(hour=15)


def test_idle_episode_key_is_stable_across_days_and_changes_after_user_activity():
    now = datetime(2030, 1, 10, 12, tzinfo=timezone.utc)
    last = now - timedelta(days=8)
    settings = Settings(inactivity_days=3)
    assert inactivity_slot(last, settings, now)[0] == inactivity_slot(last, settings, now + timedelta(days=1))[0]
    assert inactivity_slot(last + timedelta(days=1), settings, now)[0] != inactivity_slot(last, settings, now)[0]


def test_inactivity_skips_nonexistent_local_clock_time():
    now = datetime(2030, 3, 10, 12, tzinfo=timezone.utc)
    settings = Settings(timezone="America/New_York", inactivity_days=3, inactivity_time="02:30")
    assert inactivity_slot(now - timedelta(days=4), settings, now) is None


@pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")
def test_inactivity_deduplicates_and_cancels_when_user_returns(monkeypatch):
    now = datetime(2030, 1, 10, 20, tzinfo=timezone.utc)
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(service, "now_utc", lambda: now)

    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            last = now - timedelta(days=8)
            settings = Settings(timezone="UTC", inactivity_days=3)
            profile.settings = settings.model_dump(mode="json")
            profile.created_at = profile.updated_at = last
            chat = AIChat(user_id=user.id, conversation_id="test-idle", current_tokens=0, total_tokens=0)
            db.add(chat)
            await db.flush()
            db.add(AIMessage(user_id=user.id, chat_id=chat.id, sender=MessageSender.AI, text="Earlier reminder", created_at=now - timedelta(hours=1)))
            await db.flush()
            assert await last_user_activity(db, profile, now) == last
            await schedule_inactivity(db, profile, settings, now)
            await db.flush()
            await schedule_inactivity(db, profile, settings, now + timedelta(days=1))
            await db.flush()
            rows = list((await db.execute(select(AICompanionReminder).where(AICompanionReminder.user_id == user.id, AICompanionReminder.kind == "inactivity"))).scalars())
            assert len(rows) == 1
            assert await reminder_text(db, rows[0], profile)
            db.add(AIMessage(user_id=user.id, chat_id=chat.id, sender=MessageSender.USER, text="Returned", created_at=now))
            await db.flush()
            assert await reminder_text(db, rows[0], profile) is None
            profile.settings = Settings().model_dump(mode="json")
            assert await reminder_text(db, rows[0], profile) is None

    asyncio.run(run())
