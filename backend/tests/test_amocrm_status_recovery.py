"""Real delivery claims and worker recovery, isolated in a disposable PostgreSQL schema."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src import database
from src.app.modules.webhooks import router, service
from src.database.models import DeliveryAddress, DeliveryRecipient, Order, User, WebhookDelivery
from src.integrations.amocrm.constants import STATUS_IDS, STATUS_WORDS


MAIN = STATUS_IDS["main"]
TARGET = STATUS_IDS["packaged"]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def crm(monkeypatch):
    url = database.engine.url
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (url.database == "test" or url.database.endswith("_test")):
        pytest.skip("requires a local test PostgreSQL database")
    schema = f"webhook_test_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA {schema}"))
        async with engine.begin() as conn:
            await conn.run_sync(database.Base.metadata.create_all)
        async with sessions.begin() as db:
            user = User(name="Synthetic", surname="Buyer", password_hash="unused")
            db.add(user)
            await db.flush()
            address = DeliveryAddress(user_id=user.id, mode="door", provider="CDEK", country_code="RU",
                                      name="Test", full_address="Test", latitude=0, longitude=0)
            recipient = DeliveryRecipient(user_id=user.id, name="Synthetic", surname="Recipient")
            db.add_all([address, recipient])
            await db.flush()
            refs = dict(user_id=user.id, recipient_id=recipient.id, delivery_address_id=address.id)

        async def create_order(*, oid=101, code="EP-SYNTH001", lead_id=None, **fields):
            fields.setdefault("created_at", datetime.now(timezone.utc) - timedelta(minutes=2))
            async with sessions.begin() as db:
                db.add(Order(id=oid, order_code=code, amocrm_lead_id=lead_id, **refs, **fields))

        async def get_db():
            async with sessions() as db:
                yield db

        async def rows():
            async with sessions() as db:
                return list((await db.scalars(select(WebhookDelivery).order_by(WebhookDelivery.id))).all())

        monkeypatch.setattr(database, "SessionLocal", sessions)
        monkeypatch.setattr(service, "AMOCRM_WEBHOOK_ALLOWED_ACCOUNT_IDS", ["synthetic"])
        monkeypatch.setattr(service, "AMOCRM_WEBHOOK_ALLOWED_SUBDOMAINS", ["test-shop"])
        monkeypatch.setattr(service, "AMOCRM_WEBHOOK_ALLOWED_IPS", [])
        monkeypatch.setattr(router, "enforce_rate_limit", AsyncMock())
        get_lead = AsyncMock()
        async def read_lead(lead_id):
            return {"id": lead_id, "pipeline_id": router.amocrm_client.PIPELINE_ID, **await get_lead(lead_id)}
        monkeypatch.setattr(router.amocrm_client, "get_lead", read_lead)
        apply = AsyncMock(side_effect=lambda db, *, order, status_id: order)
        monkeypatch.setattr(router, "apply_amocrm_status_update", apply)
        app = FastAPI()
        app.include_router(router.webhooks_router)
        app.dependency_overrides[database.get_db] = get_db
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
            async def post(*ids, target=TARGET, previous=MAIN, event_time=None, extra_fields=None):
                fields = {"account[id]": "synthetic", "account[subdomain]": "test-shop"}
                for idx, lead_id in enumerate(ids):
                    fields[f"leads[status][{idx}][id]"] = str(lead_id)
                    fields[f"leads[status][{idx}][pipeline_id]"] = str(router.amocrm_client.PIPELINE_ID)
                    fields[f"leads[status][{idx}][status_id]"] = str(target)
                    if previous:
                        fields[f"leads[status][{idx}][old_status_id]"] = str(previous)
                    if event_time is not None:
                        fields[f"leads[status][{idx}][last_modified]"] = str(event_time)
                return await client.post("/webhooks/amocrm", data={**fields, **(extra_fields or {})})

            yield SimpleNamespace(post=post, create_order=create_order, get_lead=get_lead, apply=apply,
                                  rows=rows, sessions=sessions)
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("name,link", [
    ("Renamed lead", {"lead_id": 51}),
    ("Заказ №EP-SYNTH001 с Приложения", {"code": "EP-SYNTH001"}),
    ("Заказ №101 с Приложения", {"code": "101"}),
])
async def test_missing_order_is_durable_and_applied_when_it_appears(crm, name, link):
    crm.get_lead.return_value = {"name": name, "status_id": TARGET}
    response = await crm.post(51)
    assert response.status_code == 200 and response.json()["deferred"] == "awaiting_order"
    row, = await crm.rows()
    assert row.status == "awaiting_order"
    assert row.payload_json["event"]["leads[status][0][status_id]"] == [str(TARGET)]
    assert row.lease_until is None
    assert (await crm.post(51)).status_code == 200
    assert await router.retry_due_webhook_deliveries() == 0
    crm.get_lead.assert_awaited_once()
    crm.apply.assert_not_awaited()

    await crm.create_order(**link)
    assert await router.retry_due_webhook_deliveries() == 1
    assert (await crm.post(51)).status_code == 200
    row, = await crm.rows()
    assert row.status == "processed" and row.attempts == 2
    assert crm.apply.await_args.kwargs["order"].id == 101
    assert crm.apply.await_args.kwargs["status_id"] == TARGET
    crm.apply.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize("name,other_link", [
    ("Website №101", None),
    ("Website №EP-SYNTH001", None),
    ("Заказ №101 с Приложения", None),
    ("Заказ №EP-SYNTH001", 900),
])
async def test_unrelated_number_or_conflicting_lead_is_never_applied(crm, name, other_link):
    await crm.create_order(lead_id=other_link)
    crm.get_lead.return_value = {"name": name, "status_id": TARGET}
    assert (await crm.post(51)).json()["deferred"] == "awaiting_order"
    assert await router.retry_due_webhook_deliveries() == 0
    crm.apply.assert_not_awaited()


@pytest.mark.parametrize("name,tags,expected", [
    ("[elixirpeptide.ru] 12345", [], True),
    ("[ElixirPeptide.ru] №12345", [], True),
    ("Заказ №12345 с сайта elixirpeptide.ru", [], True),
    ("Renamed", [{"name": " ЗАКАЗ  С САЙТА "}], True),
    ("Renamed", [{"name": "заказ с elixirpeptide.ru"}], True),
    ("[elixirpeptide.ru] support", [], False),
    ("[elıxırpeptıde.ru] 12345", [], False),
    ("Заказ звонка с сайта", [], False),
    ("Renamed", [{"name": "не заказ с сайта"}], False),
    ("Renamed", [{"name": "заказ с сайта"}, {"name": "заказ с приложения"}], False),
    ("Заказ №12345 с сайта", [{"name": "заказ с приложения"}], False),
    ("Заказ №EP-SYNTH001 с Приложения", [{"name": "заказ с сайта"}], False),
    ("Заказ №EP-SYNTH001 с приложения", [{"name": "заказ с сайта"}], False),
    (None, [None, 123, {"name": ["заказ с сайта"]}], False),
    (123, {"name": "заказ с сайта"}, False),
])
def test_verified_website_source(name, tags, expected):
    assert service.amocrm_website_order({"name": name, "_embedded": {"tags": tags}}) is expected


@pytest.mark.anyio
@pytest.mark.parametrize("source", [{"name": "Заказ №12345 с сайта"},
                                    {"name": "Renamed", "_embedded": {"tags": [{"name": "заказ с сайта"}]}}])
async def test_verified_website_order_is_not_queued_but_existing_app_link_wins(crm, source):
    crm.get_lead.return_value = {**source, "status_id": TARGET}
    assert (await crm.post(51)).json()["ignored"] == "website_order"
    assert (await crm.rows())[0].status == "processed"
    assert await router.retry_due_webhook_deliveries() == 0
    crm.apply.assert_not_awaited()
    await crm.create_order(lead_id=52)
    assert (await crm.post(52)).status_code == 200
    crm.apply.assert_awaited_once()


@pytest.mark.anyio
async def test_callback_website_markers_do_not_override_unclassified_current_lead(crm):
    crm.get_lead.return_value = {"name": {"invalid": True}, "_embedded": "invalid", "status_id": TARGET}
    response = await crm.post(51, extra_fields={"leads[status][0][name]": "Заказ №12345 с сайта",
                                                "leads[status][0][tags][0][name]": "заказ с сайта"})
    assert response.json()["deferred"] == "awaiting_order"
    assert (await crm.rows())[0].status == "awaiting_order"
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
async def test_app_link_committed_during_website_lookup_wins(crm):
    source = {"name": "Заказ №12345 с сайта", "status_id": TARGET}

    async def link_before_read_returns(lead_id):
        await crm.create_order(lead_id=lead_id)
        crm.get_lead.side_effect = None
        crm.get_lead.return_value = source
        return source

    crm.get_lead.side_effect = link_before_read_returns
    assert (await crm.post(51)).json()["order_id"] == 101
    crm.apply.assert_awaited_once()


@pytest.mark.anyio
async def test_batch_tracks_unmatched_and_linked_statuses_independently(crm):
    await crm.create_order(lead_id=52)
    crm.get_lead.return_value = {"name": "Synthetic lead", "status_id": TARGET}
    assert (await crm.post(51, 52)).status_code == 200
    assert sorted(row.status for row in await crm.rows()) == ["awaiting_order", "processed", "processed"]
    assert (await crm.post(51, 52)).status_code == 200
    crm.apply.assert_awaited_once()
    await crm.create_order(oid=102, code="EP-SYNTH002", lead_id=51)
    assert await router.retry_due_webhook_deliveries() == 1
    assert [call.kwargs["order"].id for call in crm.apply.await_args_list] == [101, 102]


@pytest.mark.anyio
async def test_upstream_failure_keeps_batch_retryable_and_other_lead_can_progress(crm):
    await crm.create_order(lead_id=52)
    crm.get_lead.side_effect = [HTTPException(503, "CRM unavailable"), {"name": "Second", "status_id": TARGET}]
    assert (await crm.post(51, 52)).status_code == 503
    assert sorted(row.status for row in await crm.rows()) == ["failed", "failed", "processed"]
    crm.apply.assert_awaited_once()
    crm.get_lead.side_effect = None
    crm.get_lead.return_value = {"name": "First", "status_id": TARGET}
    assert (await crm.post(51, 52)).status_code == 200
    crm.apply.assert_awaited_once()
    assert sorted(row.status for row in await crm.rows()) == ["awaiting_order", "processed", "processed"]


@pytest.mark.anyio
async def test_storage_failure_never_acknowledges_missing_order(crm, monkeypatch):
    crm.get_lead.return_value = {"name": "Synthetic lead", "status_id": TARGET}
    monkeypatch.setattr(router, "defer_amocrm_delivery", AsyncMock(side_effect=RuntimeError("storage unavailable")))
    assert (await crm.post(51)).status_code == 500
    row, = await crm.rows()
    assert row.status == "processing" and row.lease_until is not None
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("attempts", [12, 13])
async def test_exhausted_legacy_503_is_never_automatically_reopened(crm, attempts):
    crm.get_lead.side_effect = HTTPException(503)
    assert (await crm.post(51)).status_code == 503
    async with crm.sessions.begin() as db:
        row = (await db.scalars(select(WebhookDelivery))).one()
        row.attempts = attempts
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    crm.get_lead.side_effect = None
    crm.get_lead.return_value = {"name": "Synthetic lead", "status_id": TARGET}
    await crm.create_order(lead_id=51)
    assert await router.retry_due_webhook_deliveries() == 0
    assert (await crm.post(51)).status_code == 409
    row, = await crm.rows()
    assert row.attempts == attempts and row.status == "failed"
    crm.get_lead.assert_awaited_once()
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("reason", ["callback_not_current", "previous_status_mismatch", "backward_transition",
                                    "terminal_order", "event_predates_order", "conflicting_lead_link"])
async def test_unsafe_transitions_and_identities_stay_in_review(crm, reason):
    target, previous, live = TARGET, MAIN, TARGET
    fields = {"lead_id": 51}
    if reason == "callback_not_current":
        live = STATUS_IDS["package_sent"]
    elif reason == "previous_status_mismatch":
        previous = STATUS_IDS["pending_payment"]
    elif reason == "backward_transition":
        previous = STATUS_IDS["package_sent"]
        fields.update(status=STATUS_WORDS[previous], is_shipped=True)
    elif reason == "terminal_order":
        previous = STATUS_IDS["canceled"]
        fields.update(status=STATUS_WORDS[previous], is_canceled=True, is_active=False)
    elif reason == "event_predates_order":
        fields.update(created_at=datetime.now(timezone.utc) + timedelta(minutes=1))
    elif reason == "conflicting_lead_link":
        fields["lead_id"] = 900
    await crm.create_order(**fields)
    crm.get_lead.return_value = {"name": "Заказ №EP-SYNTH001 с Приложения", "status_id": live}
    assert (await crm.post(51, target=target, previous=previous)).json()["retained"] == "needs_review"
    row, = await crm.rows()
    assert row.status == "needs_review" and row.last_error == reason
    assert (await crm.post(51, target=target, previous=previous)).status_code == 200
    assert await router.retry_due_webhook_deliveries() == 0
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["awaiting_order", "failed"])
async def test_stale_receipt_never_applies_on_recovery(crm, state):
    crm.get_lead.return_value = {"name": "Renamed", "status_id": TARGET}
    if state == "failed":
        crm.get_lead.side_effect = HTTPException(503)
    response = await crm.post(51)
    assert response.status_code == (503 if state == "failed" else 200)
    async with crm.sessions.begin() as db:
        row = (await db.scalars(select(WebhookDelivery))).one()
        row.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await crm.create_order(lead_id=51)
    assert await router.retry_due_webhook_deliveries() == 1
    row, = await crm.rows()
    assert (row.status, row.last_error) == ("needs_review", "receipt_outside_reconciliation_window")
    crm.get_lead.assert_awaited_once()
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("age", [-7200, 7200, None])
async def test_invalid_or_out_of_window_source_dates_are_retained(crm, age):
    stamp = "invalid" if age is None else int(datetime.now(timezone.utc).timestamp()) - age
    assert (await crm.post(51, event_time=stamp)).json()["retained"] == "needs_review"
    assert (await crm.rows())[0].last_error == "invalid_or_stale_event_time"
    crm.get_lead.assert_not_awaited()
    crm.apply.assert_not_awaited()


@pytest.mark.anyio
async def test_missing_remote_status_stays_retryable_instead_of_using_old_payload(crm):
    await crm.create_order(lead_id=51)
    crm.get_lead.return_value = {"name": "Renamed"}
    assert (await crm.post(51)).status_code == 503
    assert (await crm.rows())[0].status == "failed"
    crm.apply.assert_not_awaited()
    crm.get_lead.return_value["status_id"] = TARGET
    assert (await crm.post(51)).status_code == 200
    assert (await crm.rows())[0].status == "processed"
    crm.apply.assert_awaited_once()


@pytest.mark.anyio
async def test_overlapping_callbacks_read_crm_in_order_lock_order(crm, monkeypatch):
    sent = STATUS_IDS["package_sent"]
    await crm.create_order(lead_id=51, status=STATUS_WORDS[TARGET])
    first_read, release_read, second_lock = asyncio.Event(), asyncio.Event(), asyncio.Event()
    real_refresh = AsyncSession.refresh

    async def refresh(session, item, *args, **kwargs):
        if isinstance(item, Order) and kwargs.get("with_for_update") and first_read.is_set():
            second_lock.set()
        return await real_refresh(session, item, *args, **kwargs)

    async def read(lead_id):
        first_read.set()
        await release_read.wait()
        return {"status_id": sent}

    async def persist(db, *, order, status_id):
        order.status = STATUS_WORDS[status_id]
        await db.commit()
        return order

    monkeypatch.setattr(AsyncSession, "refresh", refresh)
    crm.get_lead.side_effect = read
    crm.apply.side_effect = persist
    async with asyncio.timeout(10):
        async with asyncio.TaskGroup() as tasks:
            new = tasks.create_task(crm.post(51, target=sent, previous=TARGET))
            await first_read.wait()
            old = tasks.create_task(crm.post(51, target=TARGET))
            await second_lock.wait()
            crm.get_lead.assert_awaited_once()
            release_read.set()
    assert new.result().json()["status_id"] == sent
    assert old.result().json()["retained"] == "needs_review"
    crm.apply.assert_awaited_once()
    async with crm.sessions() as db:
        assert (await db.get(Order, 101)).status == STATUS_WORDS[sent]
