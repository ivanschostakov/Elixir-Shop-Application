import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from src.app.main import app
from src.app.modules.auth.dependencies import get_current_user
from src.app.services.benefits import settlement as service

CID = UUID("a0fd6510-46d5-11f1-0a80-1550000d0718")
NOW = 1780000000


def card(program="Реферальная"):
    return {"id": str(CID), "salesAmount": 25900000, "bonusPoints": 999999,
            "attributes": [{"id": service.PROGRAM_ATTRIBUTE_ID, "value": {"name": program}}]}


def report(balance=1695500):
    return {"counterparty": {"id": str(CID)}, "balance": balance}


class Redis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, nx=False, ex=None):
        assert ex is not None
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def eval(self, script, count, key, token):
        if self.data.get(key) == token:
            del self.data[key]


class Client:
    base_url = "https://example.test"

    def __init__(self, handler):
        self.http = httpx.AsyncClient(base_url=self.base_url, transport=httpx.MockTransport(handler))

    def is_configured(self):
        return True

    async def client(self):
        return self.http


@pytest.mark.parametrize("program,expected", [("Реферальная", 2), ("Накопительная", 1), ("Нулевая", 0), ("", None), ("unknown", None)])
def test_program_is_explicit_and_unknown_never_becomes_bonus(program, expected):
    value = service.parse_settlement(card(program), report(), expected_id=CID, now=NOW)
    assert value.loyalty_program == expected
    assert value.balance_rubles == Decimal("16955.00")
    assert value.total_purchases_rubles == Decimal("259000.00")


@pytest.mark.parametrize("amount", [-10000025, 0, 12345.67])
def test_balance_keeps_sign_and_kopecks(amount):
    value = service.parse_settlement(card(), report(amount), expected_id=CID, now=NOW)
    assert value.balance_rubles == (Decimal(str(amount)) / 100).quantize(Decimal("0.01"))


@pytest.mark.parametrize("amount", [None, True, "NaN", "Infinity", "garbage"])
def test_invalid_balance_is_not_zero(amount):
    with pytest.raises(ValueError):
        service.parse_settlement(card(), report(amount), expected_id=CID, now=NOW)


def test_mismatched_identity_is_rejected():
    with pytest.raises(ValueError):
        service.parse_settlement(card(), {**report(), "counterparty": {"id": "other"}}, expected_id=CID, now=NOW)


def test_read_is_cached_and_never_writes_upstream():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            assert request.method == "GET"
            return httpx.Response(200, json=report() if "/report/" in request.url.path else card())
        redis, client = Redis(), Client(handler)
        first = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW)
        second = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW + 10)
        assert first == second
        assert len(calls) == 2
        await client.http.aclose()
    asyncio.run(run())


def test_failed_refresh_retains_balance_and_backs_off():
    async def run():
        failing = False
        calls = []
        def handler(request):
            calls.append(request)
            if failing:
                return httpx.Response(503)
            return httpx.Response(200, json=report(-98765) if "/report/" in request.url.path else card())
        redis, client = Redis(), Client(handler)
        await service.get_account_settlement(CID, redis=redis, client=client, now=NOW)
        redis.data = {k: v for k, v in redis.data.items() if not k.endswith(":gate")}
        failing = True
        result = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW + 600)
        assert result.status == "stale"
        assert result.balance_rubles == Decimal("-987.65")
        assert result.fetched_at.timestamp() == NOW
        again = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW + 601)
        assert again.status == "stale"
        assert len(calls) == 3
        await client.http.aclose()
    asyncio.run(run())


def test_rate_limit_pauses_other_customers_too():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "120"})
        redis, client = Redis(), Client(handler)
        result = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW)
        assert result.status == "unavailable"
        assert result.balance_rubles is None
        result = await service.get_account_settlement(UUID(int=1), redis=redis, client=client, now=NOW)
        assert result.issue == "rate_limited"
        assert len(calls) == 1
        await client.http.aclose()
    asyncio.run(run())


def test_unlinked_does_not_search_or_create_client():
    value = asyncio.run(service.get_account_settlement(None))
    assert value.status == "unlinked"
    assert value.balance_rubles is None
    assert value.loyalty_program is None


def test_cache_outage_does_not_call_upstream():
    class BrokenRedis(Redis):
        async def get(self, key):
            raise ConnectionError("Redis unavailable")

    async def run():
        def handler(request):
            pytest.fail("A cache outage must not trigger unbounded upstream requests")
        client = Client(handler)
        try:
            value = await service.get_account_settlement(CID, redis=BrokenRedis(), client=client, now=NOW)
            assert value.status == "unavailable"
            assert value.balance_rubles is None
            assert value.issue == "cache_unavailable"
        finally:
            await client.http.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("status,issue", [(401, "refresh_failed"), (404, "counterparty_missing"), (503, "refresh_failed")])
def test_upstream_error_never_becomes_zero_and_releases_lock(status, issue):
    async def run():
        redis, client = Redis(), Client(lambda request: httpx.Response(status))
        try:
            value = await service.get_account_settlement(CID, redis=redis, client=client, now=NOW)
            assert value.status == "unavailable"
            assert value.balance_rubles is None
            assert value.issue == issue
            assert not any(key.endswith(":lock") for key in redis.data)
        finally:
            await client.http.aclose()
    asyncio.run(run())


def test_concurrent_reads_are_coalesced():
    async def run():
        calls = []
        async def handler(request):
            calls.append(request)
            await asyncio.sleep(0.01)
            return httpx.Response(200, json=report() if "/report/" in request.url.path else card())
        redis, client = Redis(), Client(handler)
        results = await asyncio.gather(*(service.get_account_settlement(CID, redis=redis, client=client, now=NOW) for _ in range(10)))
        assert len(calls) == 2
        assert sum(result.status == "fresh" for result in results) == 1
        await client.http.aclose()
    asyncio.run(run())


def test_endpoint_requires_login_and_uses_current_user_link(monkeypatch):
    from src.app.modules.users.me import referral_profile as route
    http = TestClient(app)
    assert http.get("/api/v1/users/me/referral-profile/settlement").status_code == 401
    async def read(cid):
        assert cid == CID
        return service.parse_settlement(card("Нулевая"), report(-12345), expected_id=CID, now=NOW)
    monkeypatch.setattr(route, "get_account_settlement", read)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(moysklad_counterparty_id=CID)
    response = http.get("/api/v1/users/me/referral-profile/settlement?user_id=999")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["balance_rubles"] == "-123.45"
    assert response.json()["loyalty_program"] == 0
