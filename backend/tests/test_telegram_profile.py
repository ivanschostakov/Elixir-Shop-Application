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
            from src.app.services.ai.companion.service import grant_consent
            from src.app.services.ai.companion.schemas import Action
            import config
            await grant_consent(db, user.id, Action(kind="enable", request_key="consent-test-1", adult_confirmed=True, consent_version=config.AI_COMPANION_CONSENT_VERSION))
            db.add(AICompanionEntry(user_id=user.id, kind="weight", occurred_at=datetime.now(timezone.utc), data={"weight_kg": "110"}))
            await db.flush()
            imported = await context(Identity(telegram_user_id=user.telegram_user_id), db)
            assert imported["profile"] == {"age": 19, "height_cm": 183, "target_weight_kg": 90, "goal": "weight_loss", "current_weight_kg": 110}
            assert imported["version"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("enabled,consent", [(False, True), (True, False)])
def test_legacy_fallback_stops_before_reading_weight_without_active_consent(monkeypatch, enabled, consent):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.modules.telegram_ai import profile
    from src.app.services.ai.companion import service
    rows = [SimpleNamespace(id=5, is_active=True), SimpleNamespace(enabled=enabled, data={"age": 40})]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda row=row: row) for row in rows]))
    monkeypatch.setattr(service, "consent_for", AsyncMock(return_value=object()))
    monkeypatch.setattr(service, "consent_is_current", lambda _: consent)
    assert asyncio.run(profile.legacy_profile(db, 123)) == {}
    assert db.execute.await_count == 2


def test_legacy_maps_custom_goal_and_filters_future_weights(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.modules.telegram_ai import profile
    from src.app.services.ai.companion import service
    rows = [SimpleNamespace(id=5, is_active=True), SimpleNamespace(enabled=True, data={"goal": "custom", "custom_goal": "Run comfortably"}), None]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[SimpleNamespace(scalar_one_or_none=lambda row=row: row) for row in rows]))
    monkeypatch.setattr(service, "consent_for", AsyncMock(return_value=object()))
    monkeypatch.setattr(service, "consent_is_current", lambda _: True)
    assert asyncio.run(profile.legacy_profile(db, 123)) == {"goal": "custom", "goal_detail": "Run comfortably"}
    query = str(db.execute.await_args.args[0])
    assert "occurred_at <=" in query


def test_inactive_app_account_cannot_bypass_with_local_profile():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.app.modules.telegram_ai import profile
    inactive = SimpleNamespace(id=5, is_active=False)
    db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(data={"age": 40}, version=2)),
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: inactive)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(profile.snapshot(db, 123))
    assert error.value.status_code == 403


def test_database_inheritance_respects_revocation_future_weight_and_explicit_null():
    from test_ai_companion_db import database, URL
    if not URL:
        pytest.skip("Parent runs isolated PostgreSQL tests serially")
    from datetime import datetime, timedelta, timezone
    from src.database.models import TelegramAIProfile
    from src.database.models.ai.companion import AICompanionProfile, AICompanionEntry
    from src.app.services.ai.companion.service import grant_consent, revoke_consent
    from src.app.services.ai.companion.schemas import Action
    import config
    async def run():
        async with database() as (db, user):
            user.telegram_user_id = 88000000109
            app_profile = AICompanionProfile(user_id=user.id, enabled=True, data={"age": 40, "goal": "custom", "custom_goal": "Strength"}, settings={})
            db.add(app_profile)
            db.add(TelegramAIProfile(telegram_user_id=user.telegram_user_id, version=1, data={"age": None}, receipts=[]))
            instant = datetime.now(timezone.utc)
            db.add(AICompanionEntry(user_id=user.id, kind="weight", occurred_at=instant-timedelta(days=1), data={"weight_kg": 80}))
            db.add(AICompanionEntry(user_id=user.id, kind="weight", occurred_at=instant+timedelta(days=1), data={"weight_kg": 99}))
            await grant_consent(db, user.id, Action(kind="enable", request_key="consent-fallback", adult_confirmed=True, consent_version=config.AI_COMPANION_CONSENT_VERSION))
            await db.flush()
            identity = Identity(telegram_user_id=user.telegram_user_id)
            inherited = (await context(identity, db))["profile"]
            assert inherited["age"] is None and inherited["current_weight_kg"] == 80
            assert inherited["goal_detail"] == "Strength"
            await revoke_consent(db, user.id)
            assert (await context(identity, db))["profile"] == {"age": None}
            user.is_active = False
            await db.flush()
            with pytest.raises(HTTPException) as error:
                await context(identity, db)
            assert error.value.status_code == 403
    asyncio.run(run())
