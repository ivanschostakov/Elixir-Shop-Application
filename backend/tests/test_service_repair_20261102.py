import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.app.services.benefits import loyalty
from src.integrations.moysklad.client import MoySkladClient


def test_community_ingest_lock_serializes_real_postgres_sessions():
    from src.database import engine
    from src.app.services.community.common import lock_community_ingest
    async def run():
        isolated = create_async_engine(engine.url)
        sessions = async_sessionmaker(isolated)
        try:
            async with sessions() as first, sessions() as second:
                await lock_community_ingest(first, -10020261102)
                statement = select(func.pg_try_advisory_xact_lock(1129270612, func.hashtext("-10020261102")))
                assert (await second.execute(statement)).scalar_one() is False
                await first.rollback()
                assert (await second.execute(statement)).scalar_one() is True
        finally:
            await isolated.dispose()
    asyncio.run(run())


@pytest.mark.parametrize("phone", ["79298472035", "+79298472035", "+7 (929) 847-20-35"])
def test_moysklad_phone_identity_ignores_only_formatting(phone):
    assert MoySkladClient._counterparty_phone_matches({"phone": phone}, "+79298472035")
    assert MoySkladClient._counterparty_phone_matches({"contactpersons": {"rows": [{"phone": phone}]}}, "+79298472035")


@pytest.mark.parametrize("phone", [None, "", "123", "+79298472036", "79298472035,79298472036", "доб.79298472035"])
def test_phone_matching_never_treats_missing_or_ambiguous_numbers_as_identity(phone):
    assert not MoySkladClient._counterparty_phone_matches({"phone": phone}, "+79298472035")
    assert not MoySkladClient._counterparty_phone_matches({"phone": None}, None)


def test_duplicate_phone_cards_are_still_ambiguous():
    client = MoySkladClient(token="test")
    client.get_page = AsyncMock(return_value={"rows": [
        {"id": "one", "phone": "79298472035"},
        {"id": "two", "phone": "+79298472035"},
    ]})
    assert asyncio.run(client.get_counterparty_by_phone("+79298472035")) is None


def test_identity_conflict_is_parked_without_creating_a_contact_or_payment(monkeypatch):
    user = SimpleNamespace(id=69, email="customer@example.com", moysklad_counterparty_id=None)
    credit = SimpleNamespace(id=41, user_id=69, status="pending", source_kind="welcome")
    db = SimpleNamespace(get=AsyncMock(side_effect=[user, credit]), rollback=AsyncMock(), commit=AsyncMock())
    client = MoySkladClient(token="test")
    client.get_page = AsyncMock(return_value={"rows": [{"id": "one", "email": user.email}, {"id": "two", "email": user.email}]})
    client.resolve_or_sync_counterparty = AsyncMock()
    payment = AsyncMock()
    monkeypatch.setattr("src.app.services.auth.service._link_moysklad_counterparty_by_email", AsyncMock())
    monkeypatch.setattr(loyalty, "create_bonus_balance_payment", payment)
    assert asyncio.run(loyalty._sync_balance_credit(db, credit=credit, client=client)) is False
    assert credit.status == "identity_review"
    assert "manual identity" in credit.sync_error
    client.resolve_or_sync_counterparty.assert_not_awaited()
    payment.assert_not_awaited()


def test_reviewed_credit_is_not_retried_until_a_contact_is_linked(monkeypatch):
    credit = SimpleNamespace(status="identity_review")
    sync = AsyncMock()
    monkeypatch.setattr(loyalty, "_credit_by_key", AsyncMock(return_value=credit))
    monkeypatch.setattr(loyalty, "sync_loyalty_bonus_credit", sync)
    kwargs = dict(source_kind="welcome", idempotency_key="welcome:user:69", points=1000)
    user = SimpleNamespace(moysklad_counterparty_id=None)
    assert asyncio.run(loyalty.create_loyalty_bonus_credit(None, user=user, **kwargs)) is credit
    sync.assert_not_awaited()
    user.moysklad_counterparty_id = "confirmed-id"
    asyncio.run(loyalty.create_loyalty_bonus_credit(None, user=user, **kwargs))
    sync.assert_awaited_once()
