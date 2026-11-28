import asyncio
import os
from decimal import Decimal
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import config
from src.app.services import counterparty_review
from src.app.services.admin.jobs import is_retryable_error, retry_delay_for_error
from src.app.services.auth.service import counterparty as auth
from src.app.services.orders import payments, settlement_payment
from src.app.services.referrals import registration
from src.database.models import AdminAlert
from src.integrations.moysklad.client import MoySkladClient
from src.integrations.moysklad.client.rate_limit import MoySkladRateLimited, PacedMoySkladClient
from src.integrations.moysklad.identity import CounterpartyReviewRequired
from src.integrations.moysklad.order_sync.service import _mark_remote_export

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_writes_not_replayed_and_other_routes_respect_pause(method):
    calls = []
    def endpoint(request):
        calls.append(request.method)
        return httpx.Response(429, headers={"Retry-After": "9"})
    async with PacedMoySkladClient(credential="stub", base_url="https://example.test",
                                   transport=httpx.MockTransport(endpoint)) as client:
        with pytest.raises(MoySkladRateLimited):
            await client.request(method, "/entity/paymentin")
        with pytest.raises(MoySkladRateLimited) as error:
            await client.get("/entity/currency")
        assert int(error.value.response.headers["Retry-After"]) >= 8
        assert calls == [method]


async def test_get_retries_only_once_then_defers():
    remote = AsyncMock(side_effect=lambda request: httpx.Response(429, headers={"Retry-After": "0"}))
    async with PacedMoySkladClient(credential="stub", transport=httpx.MockTransport(remote)) as client:
        with pytest.raises(MoySkladRateLimited):
            await client.get("https://example.test/currency")
    assert remote.await_count == 2


async def test_parallel_requests_are_spaced_without_redis():
    starts = []
    def remote(request):
        starts.append(monotonic())
        return httpx.Response(200)
    async with PacedMoySkladClient(credential="stub", transport=httpx.MockTransport(remote)) as client:
        await asyncio.gather(*(client.get("https://example.test/read") for _ in range(4)))
    assert len(starts) == 4
    assert all(b - a >= 0.14 for a, b in zip(starts, starts[1:]))


async def test_shared_redis_pacing_cooldown_and_recovery():
    sock = os.environ.get("MOYSKLAD_TEST_REDIS_SOCKET")
    if not sock:
        pytest.skip("Set MOYSKLAD_TEST_REDIS_SOCKET to a private local Redis test socket")
    calls = []
    def remote(req):
        calls.append((req.url.path, monotonic()))
        return (httpx.Response(429, headers={"X-Lognex-Retry-After": "750"})
                if req.url.path == "/busy" else httpx.Response(200))
    key = str(uuid4())
    def process(credential):
        return PacedMoySkladClient(credential=credential, redis_url=f"unix://{sock}", base_url="https://example.test",
                                   transport=httpx.MockTransport(remote))
    async with process(key) as api, process(key) as worker, process(str(uuid4())) as other:
        await asyncio.gather(api.get("/catalog"), worker.get("/currency"))
        assert calls[1][1] - calls[0][1] >= 0.14
        with pytest.raises(MoySkladRateLimited):
            await worker.post("/busy")
        with pytest.raises(MoySkladRateLimited):
            await api.get("/deferred")
        await other.get("/independent")
        assert [path for path, _ in calls[2:]] == ["/busy", "/independent"]
        await asyncio.sleep(0.8)
        assert (await api.get("/resumed")).status_code == 200


async def test_worker_defers_checkout_rate_limit_but_not_review():
    req = httpx.Request("GET", "https://example.test/")
    res = httpx.Response(429, request=req, headers={"X-Lognex-Retry-After": "123001", "Retry-After": "bad"})
    error = settlement_payment.settlement_pending(rate_limit=res)
    error.__cause__ = MoySkladRateLimited("busy", request=req, response=res)
    assert is_retryable_error(error)
    assert retry_delay_for_error(error, 1) == error.detail["retry_after_seconds"] == 124
    assert not is_retryable_error(CounterpartyReviewRequired("email"))


def test_reset_header_is_respected_even_without_retry_after():
    res = httpx.Response(429, headers={"X-Lognex-Reset": "18500"})
    assert settlement_payment.settlement_pending(rate_limit=res).detail["retry_after_seconds"] == 19


async def test_currency_limit_blocks_gateway_and_read_only_probe_recovers(monkeypatch):
    monkeypatch.setattr(config, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(payments, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr(payments, "verify_no_unapproved_balance", AsyncMock())
    gateway = AsyncMock()
    monkeypatch.setattr(payments.intellectmoney, "create_invoice", gateway)
    monkeypatch.setattr(payments, "_payment_status_payload", lambda order: {})
    oid, iid, cid, org, currency = [str(UUID(int=i)) for i in range(1, 6)]
    shared = dict(applicable=True, sum=10000, agent={"id": cid}, organization={"id": org},
                  rate={"currency": {"id": currency}, "value": 1})
    req = httpx.Request("GET", "https://example.test/currency")
    currency_get = AsyncMock(side_effect=[httpx.Response(429, request=req, headers={"Retry-After": "17"}),
        httpx.Response(429, request=req, headers={"Retry-After": "17"}),
        httpx.Response(200, request=req, json={"id": currency, "isoCode": "RUB", "code": "643"})])
    ms = SimpleNamespace(get_customer_order=AsyncMock(return_value=dict(shared, id=oid, invoicesOut=[{"id": iid}])),
        get_invoiceout=AsyncMock(return_value=dict(shared, id=iid, customerOrder={"id": oid})),
        client=AsyncMock(return_value=SimpleNamespace(get=currency_get)))
    monkeypatch.setattr(settlement_payment, "get_moysklad_client", lambda: ms)
    order = SimpleNamespace(is_paid=False, is_canceled=False, payment_status="draft", payment_provider=None,
        payment_method="sbp", payment_invoice_id=None, grand_total=Decimal(100),
        moysklad_customerorder_id=UUID(oid), moysklad_invoiceout_id=UUID(iid),
        checkout_snapshot={"order_export_version": 1, "moysklad_document_identity": {"counterparty_id": cid, "organization_id": org}})
    for call in (payments._create_payment_for_order(None, order=order, request=None),
                 payments.get_payment_status_for_order(None, order=order, request=None, check_invoice=True)):
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 409
        assert exc.value.detail["code"] == "settlement_pending" and exc.value.detail["retry_after_seconds"] == 17
    assert (await payments.get_payment_status_for_order(None, order=order, request=None, check_invoice=True))["invoice_ready"]
    assert currency_get.await_count == 3 and order.payment_invoice_id is None
    gateway.assert_not_awaited()


async def test_duplicate_login_alert_survives_concurrency_then_merge(monkeypatch):
    # Separate pool for this asyncio loop; this also exercises the real unique constraint.
    engine = create_async_engine(config.ASYNC_DB_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(counterparty_review, "SessionLocal", sessions)
    user = SimpleNamespace(id=-(uuid4().int % 10**9), email="same@example.com", phone_number=None,
                           moysklad_counterparty_id=None)
    fp = f"moysklad:identity:customer:{user.id}"
    rows = [{"id": str(uuid4()), "email": user.email}, {"id": str(uuid4()), "email": user.email}]
    ms = MoySkladClient(token="stub")
    ms.get_page = AsyncMock(side_effect=lambda *a, **kw: {"rows": rows})
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(auth, "get_moysklad_client", lambda: ms)
    try:
        await asyncio.gather(*(auth._link_moysklad_counterparty_by_email(user, db) for _ in range(2)))
        assert user.moysklad_counterparty_id is None
        async with sessions() as read:
            alert = (await read.scalars(select(AdminAlert).where(AdminAlert.fingerprint == fp))).one()
            assert alert.occurrence_count == 2 and alert.resolved_at is None
            assert all(row["id"] in alert.message for row in rows) and user.email not in alert.message
            assert alert.path == f"/customers/{user.id}"
        db.commit.assert_not_awaited()
        rows.pop(0)
        await auth._link_moysklad_counterparty_by_email(user, db)
        assert user.moysklad_counterparty_id == UUID(rows[0]["id"])
    finally:
        async with sessions.begin() as cleanup:
            await cleanup.execute(delete(AdminAlert).where(AdminAlert.fingerprint == fp))
        await engine.dispose()


async def test_registration_conflict_keeps_existing_program_and_promo(monkeypatch):
    profile = SimpleNamespace(reward_program="partner", current_discount_percent=Decimal(6),
        reward_program_selection_source="registration", reward_program_snapshot={"registration_sync_pending": True})
    user = SimpleNamespace(id=5, is_verified=True, moysklad_counterparty_id=None, promo_code="EXISTING")
    db = SimpleNamespace(scalar=AsyncMock(return_value=5), refresh=AsyncMock(), commit=AsyncMock())
    monkeypatch.setattr(registration, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(registration, "get_referral_profile_by_user_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(registration, "_registration_counterparty", AsyncMock(side_effect=CounterpartyReviewRequired("email")))
    queue = AsyncMock()
    monkeypatch.setattr(registration, "queue_counterparty_review", queue)
    await registration.sync_registration_choice(db, user=user, best_effort=True)
    with pytest.raises(CounterpartyReviewRequired):
        await registration.sync_registration_choice(db, user=user)
    assert queue.await_count == 2 and user.moysklad_counterparty_id is None
    assert profile.reward_program_snapshot["registration_sync_pending"]
    assert (profile.reward_program, user.promo_code, profile.current_discount_percent) == ("partner", "EXISTING", 6)


async def test_export_does_not_create_duplicate_or_accept_partial_page():
    ms = MoySkladClient(token="stub")
    ms._find_entity_by_external_code = AsyncMock(return_value=None)
    ms.get_page = AsyncMock(return_value={"meta": {"size": 3}, "rows": [{"id": str(uuid4()), "email": "a@example.com"}]})
    ms._create_entity = AsyncMock()
    with pytest.raises(CounterpartyReviewRequired):
        await ms.resolve_or_sync_counterparty(existing_counterparty_id=None, external_code="app:1", sync_id=uuid4(),
            name="Test", email="a@example.com", phone=None, actual_address=None)
    ms._create_entity.assert_not_awaited()


async def test_legacy_missing_limit_fails_closed_before_export():
    order = SimpleNamespace(checkout_snapshot={"settlement_payment": {"version": 1, "gross_rubles": "500"}},
                            moysklad_customerorder_id=None)
    with pytest.raises(HTTPException) as exc:
        await _mark_remote_export(None, order, None, None)
    assert exc.value.status_code == 409


async def test_conflicted_export_is_left_for_manual_retry(monkeypatch):
    from src.integrations.moysklad.order_sync import service
    monkeypatch.setattr(service, "sync_order_to_moysklad", AsyncMock(side_effect=CounterpartyReviewRequired("email")))
    record = AsyncMock()
    monkeypatch.setattr(service, "_record_automatic_order_sync", record)
    result = await service.sync_order_to_moysklad_safe(None, order=SimpleNamespace(id=8), user=SimpleNamespace(id=9))
    assert result.skipped_reason == "identity_review"
    assert record.await_args.kwargs["status"] == "error" and not record.await_args.kwargs.get("enqueue")
