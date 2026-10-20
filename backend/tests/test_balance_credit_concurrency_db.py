import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.app.services.benefits import loyalty, settlement_cache
from src.database.models import LoyaltyBonusCredit, User


@pytest.mark.parametrize("same_credit", [True, False])
def test_concurrent_workers_cannot_credit_the_same_customer_twice(monkeypatch, same_credit):
    url = os.environ.get("BONUS_SYNC_TEST_DB_URL", "")
    if not url:
        pytest.skip("Requires disposable bonus_sync_test database")
    assert url.rsplit("/", 1)[-1] == "bonus_sync_test"
    monkeypatch.setattr(loyalty, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(settlement_cache, "invalidate_account_settlement", AsyncMock())

    async def scenario():
        engine = create_async_engine(url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        customer_id, payment_id = uuid4(), uuid4()
        users, credits = [], []
        remote = {"active": 0, "max_active": 0, "posts": 0, "payment": None}

        async def post(*args, **kwargs):
            remote["active"] += 1
            remote["max_active"] = max(remote["max_active"], remote["active"])
            try:
                await asyncio.sleep(0.1)
                if remote["payment"] is None:
                    remote["posts"] += 1
                    remote["payment"] = {"id": str(payment_id)}
                return remote["payment"]
            finally:
                remote["active"] -= 1

        monkeypatch.setattr(loyalty, "create_bonus_balance_payment", post)
        try:
            async with sessions() as db:
                for _ in range(1 if same_credit else 2):
                    user = User(email=f"{uuid4()}@example.test", password_hash="test", name="Test", surname="Customer",
                        is_verified=True, moysklad_counterparty_id=customer_id)
                    db.add(user)
                    await db.flush()
                    users.append(user.id)
                    now = datetime.now(timezone.utc)
                    credit = LoyaltyBonusCredit(user_id=user.id, source_kind="welcome", idempotency_key=f"welcome:user:{user.id}",
                        points=1000, status="pending", earned_at=now, available_at=now)
                    db.add(credit)
                    await db.flush()
                    credits.append(credit.id)
                await db.commit()

            async def sync(identifier):
                async with sessions() as db:
                    item = await db.get(LoyaltyBonusCredit, identifier)
                    return await loyalty.sync_loyalty_bonus_credit(db, credit=item,
                        client=SimpleNamespace(is_configured=lambda: True))

            assert all(await asyncio.gather(sync(credits[0]), sync(credits[-1])))
            assert remote["posts"] == 1 and remote["max_active"] == 1
            async with sessions() as db:
                rows = list((await db.scalars(select(LoyaltyBonusCredit).where(LoyaltyBonusCredit.id.in_(credits)))).all())
                assert sum(row.status == "applied" for row in rows) == 1
                if not same_credit:
                    duplicate = next(row for row in rows if row.status == "already_granted")
                    original = next(row for row in rows if row.status == "applied")
                    assert duplicate.reconciled_to_credit_id == original.id
        finally:
            async with sessions() as db:
                await db.execute(delete(LoyaltyBonusCredit).where(LoyaltyBonusCredit.id.in_(credits)))
                await db.execute(delete(User).where(User.id.in_(users)))
                await db.commit()
            await engine.dispose()

    asyncio.run(scenario())
