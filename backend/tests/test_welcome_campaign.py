from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from config import ASYNC_DB_URL
from src.app.modules.auth.schemas.login import UserLoginVerifyPayload
from src.app.services.auth.service import email
from src.app.services.benefits import app_welcome as promo
from src.app.services.benefits.backfill_app_welcome import candidates
from src.app.services.notifications import welcome
from src.database import Base
from src.database.models import EmailVerificationCode, LoyaltyBonusCredit, NotificationDispatch, User, UserDevice, UserPushToken, UserSession


@pytest.fixture
async def db():
    engine = create_async_engine(ASYNC_DB_URL)
    try:
        async with engine.connect() as conn:
            schema = "test_welcome_" + uuid4().hex
            await conn.execute(text(f"CREATE SCHEMA {schema}"))
            await conn.execute(text(f"SET LOCAL search_path TO {schema}"))
            await conn.run_sync(Base.metadata.create_all)
            async with AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
                yield session
    finally:
        await engine.dispose()


async def customer(db):
    user = User(name="Test", surname="Buyer", email=f"{uuid4().hex}@example.com",
                is_verified=True, password_hash="unused", created_at=promo.START-timedelta(days=80))
    db.add(user)
    await db.flush()
    return user


@pytest.mark.anyio
async def test_website_user_needs_mobile_code_and_cannot_renew(db, monkeypatch):
    user = await customer(db)
    now = promo.START - timedelta(microseconds=1)
    monkeypatch.setattr(promo, "ufa_now", lambda: now)
    monkeypatch.setattr(email, "_apply_auth_rate_limit", AsyncMock())
    monkeypatch.setattr(email, "_build_auth_tokens_response", AsyncMock())
    valid = AsyncMock(side_effect=HTTPException(400, "invalid"))
    monkeypatch.setattr(email, "_verify_latest_email_code", valid)
    async def verify(platform):
        request = Request({"type":"http", "headers":[(b"x-app-platform", platform.encode())]})
        return await email.verify_login_user(request, UserLoginVerifyPayload(email=user.email, code="123456"), db)
    with pytest.raises(HTTPException):
        await verify("ios")
    valid.side_effect = None
    await verify("ios")
    now = promo.START
    await verify("web")
    assert not (await db.scalars(select(LoyaltyBonusCredit))).all()
    await verify("android")
    now += timedelta(days=1)
    await verify("ios")
    credit, = (await db.scalars(select(LoyaltyBonusCredit))).all()
    assert (credit.points, credit.source_kind, credit.status) == (1000, "app_welcome", "local")
    assert credit.expires_at == promo.START + timedelta(days=5)
    assert credit.moysklad_paymentin_id is None
    notice = await welcome.pending_notice(db, user.id)
    assert notice["credit_id"] == credit.id
    await welcome.acknowledge_notice(db, user.id+1, credit.id)
    assert await welcome.pending_notice(db, user.id)
    await welcome.acknowledge_notice(db, user.id, credit.id)
    assert await welcome.pending_notice(db, user.id) is None
    now += timedelta(days=10)
    await verify("android")
    assert (await promo.wallet(db, user.id))[1] == 0


@pytest.mark.anyio
async def test_backfill_requires_first_mobile_and_matching_code(db, monkeypatch):
    t = promo.START + timedelta(minutes=30)
    monkeypatch.setattr(promo, "ufa_now", lambda: t)
    people = [await customer(db) for _ in range(6)]
    for idx, user in enumerate(people):
        db.add(UserSession(user_id=user.id, refresh_token_hash="dummy", created_at=t))
        if idx != 1:
            db.add(UserDevice(user_id=user.id, installation_id="test", platform="android", first_seen_at=t))
        if idx != 2:
            db.add(EmailVerificationCode(user_id=user.id, code_hash="unused", expires_at=t, used_at=t))
        if idx == 3:
            db.add(UserSession(user_id=user.id, refresh_token_hash="old", created_at=promo.START-timedelta(seconds=1)))
        if idx == 4:
            user.welcome_bonus_granted_at = promo.START
        if idx == 5:
            db.add(LoyaltyBonusCredit(user_id=user.id, source_kind="welcome", idempotency_key=f"welcome:user:{user.id}",
                                      points=1000, status="applied", earned_at=t, available_at=t))
    await db.flush()
    assert (await db.scalars(candidates())).all() == people[:1]
    assert await promo.grant_on_email_confirmation(db, people[3]) is None
    assert await promo.grant_on_email_confirmation(db, people[5]) is None
    assert await promo.grant_on_email_confirmation(db, people[0])
    await db.flush()
    assert not (await db.scalars(candidates())).all()


@pytest.mark.anyio
async def test_duplicate_profiles_for_one_known_customer_do_not_repeat_credit(db, monkeypatch):
    monkeypatch.setattr(promo, "ufa_now", lambda: promo.START)
    first, duplicate = await customer(db), await customer(db)
    first.moysklad_counterparty_id = duplicate.moysklad_counterparty_id = uuid4()
    await db.flush()
    assert await promo.grant_on_email_confirmation(db, first)
    assert await promo.grant_on_email_confirmation(db, duplicate) is None


@pytest.mark.anyio
async def test_five_push_windows_retry_partial_balance_and_expiry(db, monkeypatch):
    user = await customer(db)
    t = promo.START + timedelta(hours=14)
    now = t
    monkeypatch.setattr(promo, "ufa_now", lambda: now)
    await promo.grant_on_email_confirmation(db, user)
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(welcome, "send_push_to_users", send)
    assert await welcome.process_welcome_reminders(db, now=t) == 0
    db.add(UserPushToken(user_id=user.id, expo_push_token="fixture", platform="ios"))
    await db.flush()
    send.return_value = False
    assert await welcome.process_welcome_reminders(db, now=t) == 0
    send.return_value = True
    for day in range(5):
        now = t + timedelta(days=day)
        assert await welcome.process_welcome_reminders(db, now=now) == 1
        assert send.await_args.kwargs["data"]["day"] == day + 1
        assert await welcome.process_welcome_reminders(db, now=now) == 0
    now = t + timedelta(days=5)
    assert await welcome.process_welcome_reminders(db, now=now) == 0
    assert len((await db.scalars(select(NotificationDispatch))).all()) == 5


@pytest.mark.anyio
async def test_push_uses_remaining_balance_and_never_catches_up(db, monkeypatch):
    user = await customer(db)
    t = promo.START
    monkeypatch.setattr(promo, "ufa_now", lambda: t)
    await promo.grant_on_email_confirmation(db, user)
    db.add(UserPushToken(user_id=user.id, expo_push_token="test", platform="ios"))
    await db.flush()
    credit = (await db.scalars(select(LoyaltyBonusCredit))).one()
    wallet = AsyncMock(return_value=(credit, Decimal("412.50")))
    monkeypatch.setattr(promo, "wallet", wallet)
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(welcome, "send_push_to_users", send)
    assert await welcome.process_welcome_reminders(db, now=t+timedelta(days=2)) == 1
    assert "412,50" in send.await_args.kwargs["body"]
    assert send.await_args.kwargs["data"]["day"] == 3
    wallet.return_value = credit, Decimal("0")
    assert await welcome.process_welcome_reminders(db, now=t+timedelta(days=3)) == 0
    assert send.await_count == 1
