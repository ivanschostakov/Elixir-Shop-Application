import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from src.app.services.auth import service
from src.integrations.moysklad.client import MoySkladClient


CID = UUID("00000000-0000-0000-0000-000000000048")


@pytest.fixture
def sync(monkeypatch):
    client = MoySkladClient(token="test")
    card = {"id": str(CID), "email": "customer@example.com", "phone": "+7 (999) 000-11-22"}
    monkeypatch.setattr(client, "get_counterparty_by_email", AsyncMock(return_value=card))
    monkeypatch.setattr(client, "get_counterparty", AsyncMock(return_value=card))
    monkeypatch.setattr(service, "get_moysklad_client", lambda: client)
    owner = AsyncMock(return_value=None)
    monkeypatch.setattr(service, "get_user_by_phone_number", owner)
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    user = SimpleNamespace(id=48, email="customer@example.com", phone_number=None,
        moysklad_counterparty_id=None, telegram_phone_confirmed_at=None)
    return user, db, client, owner


@pytest.mark.parametrize("linked", [False, True])
def test_missing_phone_is_imported_for_new_and_existing_link(sync, linked):
    user, db, client, owner = sync
    if linked:
        user.moysklad_counterparty_id = CID
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.phone_number == "+79990001122"
    assert user.moysklad_counterparty_id == CID
    assert user.telegram_phone_confirmed_at is None
    owner.assert_awaited_once_with(db, "+79990001122")
    db.commit.assert_awaited_once()
    if linked:
        client.get_counterparty.assert_awaited_once_with(CID)
        client.get_counterparty_by_email.assert_not_awaited()
    else:
        client.get_counterparty_by_email.assert_awaited_once_with("customer@example.com")


def test_existing_phone_does_not_fetch_or_overwrite(sync):
    user, db, client, owner = sync
    user.moysklad_counterparty_id = CID
    user.phone_number = "+79990000000"
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.phone_number == "+79990000000"
    client.get_counterparty.assert_not_awaited()
    owner.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.parametrize("linked", [False, True])
def test_another_accounts_phone_is_not_imported(sync, linked):
    user, db, client, owner = sync
    user.moysklad_counterparty_id = CID if linked else None
    owner.return_value = SimpleNamespace(id=99)
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.phone_number is None
    assert user.moysklad_counterparty_id == CID
    assert db.commit.await_count == (0 if linked else 1)


@pytest.mark.parametrize("phone", [None, "", "доб.123", "+79990001122, +79990000000", "123", "1" * 16])
def test_missing_or_ambiguous_remote_phone_is_not_imported(sync, phone):
    user, db, client, owner = sync
    client.get_counterparty_by_email.return_value["phone"] = phone
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.phone_number is None
    assert user.moysklad_counterparty_id == CID
    owner.assert_not_awaited()


def test_linked_contact_does_not_switch_to_email_match(sync):
    user, db, client, owner = sync
    user.moysklad_counterparty_id = CID
    client.get_counterparty.return_value = {"id": str(UUID(int=2)), "phone": "+79990000000"}
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.moysklad_counterparty_id == CID
    assert user.phone_number is None
    owner.assert_not_awaited()
    client.get_counterparty_by_email.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_linked_remote_outage_does_not_block_login(sync):
    user, db, client, owner = sync
    user.moysklad_counterparty_id = CID
    client.get_counterparty.side_effect = RuntimeError("unavailable")
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    assert user.phone_number is None
    db.commit.assert_not_awaited()


def test_concurrent_phone_conflict_rolls_back_without_blocking_login(sync):
    user, db, client, owner = sync
    db.commit.side_effect = IntegrityError("update", {}, RuntimeError("duplicate"))

    async def refresh(target):
        target.phone_number = None
        target.moysklad_counterparty_id = None

    db.refresh.side_effect = refresh
    asyncio.run(service._link_moysklad_counterparty_by_email(user, db))
    db.rollback.assert_awaited_once()
    assert user.phone_number is None
