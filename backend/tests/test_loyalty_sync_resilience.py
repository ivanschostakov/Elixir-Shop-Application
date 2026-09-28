import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import MissingGreenlet

from src.app.services.benefits import loyalty
from src.database.models import LoyaltyBonusCredit, User


def rejection(status=412):
    request = httpx.Request('POST', 'https://example.test/entity/bonustransaction', headers={'Authorization':'Bearer SECRET'})
    response = httpx.Response(status, request=request, json={'errors':[{'code':3006,'error':"Duplicate parameter 'name'"}]})
    return httpx.HTTPStatusError('Rejected', request=request, response=response)


class ExpiringCredit(SimpleNamespace):
    def __getattribute__(self, name):
        if not name.startswith('_') and object.__getattribute__(self, '__dict__').get('_expired'):
            raise MissingGreenlet('Implicit load after rollback')
        return super().__getattribute__(name)


def credit(identifier, status='pending'):
    return ExpiringCredit(id=identifier, user_id=identifier, status=status, points=1000,
        spent_points=0, source_kind='welcome', idempotency_key=f'welcome:user:{identifier}',
        moysklad_bonus_transaction_id=None, sync_error=None,
        expires_at=datetime.now(timezone.utc)-timedelta(days=1), _expired=False)


class Db:
    def __init__(self, credits):
        self.credits = {item.id:item for item in credits}
        self.commit = AsyncMock()

    async def get(self, model, identifier, **kwargs):
        if model is User:
            return SimpleNamespace(id=identifier)
        assert model is LoyaltyBonusCredit
        result = self.credits.get(identifier)
        if result:
            result._expired = False
        return result

    async def rollback(self):
        for item in self.credits.values():
            item._expired = True

    async def execute(self, statement):
        assert [column.name for column in statement.selected_columns] == ['id']
        return SimpleNamespace(scalars=lambda:SimpleNamespace(all=lambda:list(self.credits)))


@pytest.fixture
def wallet(monkeypatch):
    wallet = SimpleNamespace(counterparty_id=uuid4(),program_id=uuid4())
    monkeypatch.setattr(loyalty,'_ensure_moysklad_wallet',AsyncMock(return_value=wallet))
    return wallet


@pytest.mark.parametrize('method,status,expected',[
    ('sync_loyalty_bonus_credit','pending','failed'),
    ('reverse_loyalty_bonus_credit','applied','reversal_pending'),
])
def test_failure_records_details_after_rollback(wallet, method, status, expected):
    item = credit(4,status)
    db = Db([item])
    client = SimpleNamespace(resolve_or_create_bonus_transaction=AsyncMock(side_effect=rejection()))
    assert asyncio.run(getattr(loyalty,method)(db,credit=item,client=client)) is False
    assert item.status == expected
    assert '3006' in item.sync_error and 'name' in item.sync_error
    assert 'SECRET' not in item.sync_error
    db.commit.assert_awaited_once()


def test_queue_continues_after_first_credit_rolls_back(wallet,monkeypatch):
    first,second = credit(4),credit(5)
    db = Db([first,second])
    client = SimpleNamespace(resolve_or_create_bonus_transaction=AsyncMock(side_effect=[rejection(),{'id':str(uuid4()),'applicable':True}]))
    monkeypatch.setattr(loyalty,'get_moysklad_client',lambda:client)
    result = asyncio.run(loyalty.sync_pending_loyalty_bonus_credits(db))
    assert result == {'processed':2,'synced':1,'failed':1}
    assert first.status == 'failed' and second.status == 'applied'
    calls = client.resolve_or_create_bonus_transaction.await_args_list
    assert calls[0].kwargs['name'] != calls[1].kwargs['name']
    for item, call in zip([first,second],calls):
        assert call.kwargs['external_code'] == loyalty._external_code(item.idempotency_key)
        assert f'#{item.id}' in call.kwargs['name']


def test_expiry_queue_continues_after_rollback(wallet,monkeypatch):
    first,second = credit(4,'applied'),credit(5,'applied')
    db = Db([first,second])
    client = SimpleNamespace(resolve_or_create_bonus_transaction=AsyncMock(side_effect=[rejection(),{'id':str(uuid4()),'applicable':True}]))
    monkeypatch.setattr(loyalty,'get_moysklad_client',lambda:client)
    result = asyncio.run(loyalty.expire_loyalty_bonus_credits(db))
    assert result == {'processed':2,'expired':1,'failed':1}
    assert '3006' in first.sync_error
    assert second.status == 'expired'


def test_already_applied_credit_does_not_create_another_transaction(wallet):
    item = credit(4,'applied')
    item.moysklad_bonus_transaction_id = uuid4()
    client = SimpleNamespace(resolve_or_create_bonus_transaction=AsyncMock())
    assert asyncio.run(loyalty.sync_loyalty_bonus_credit(Db([item]),credit=item,client=client)) is True
    client.resolve_or_create_bonus_transaction.assert_not_awaited()


@pytest.mark.parametrize('body',[b'not JSON',b'[]',b'{"errors":null}'])
def test_error_diagnostics_tolerate_invalid_bodies(body):
    request = httpx.Request('POST','https://example.test')
    response = httpx.Response(503,request=request,content=body)
    error = httpx.HTTPStatusError('Rejected',request=request,response=response)
    assert loyalty._sync_error_message(error) == 'MoySklad HTTP 503'


def test_error_diagnostics_respect_column_limit():
    assert len(loyalty._sync_error_message(RuntimeError('x'*1000))) == 500
