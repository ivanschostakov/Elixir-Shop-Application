"""Real order commits, worker sessions, advisory locks and recovery; external I/O is stubbed."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from src.app.services.admin import jobs
from src.app.services.orders import automatic_checkout as auto, payment_attempt, payments
from src.database import SessionLocal
from src.database.models import IntegrationRun, Order, User
from test_guest_checkout_api import _build_guest_order_payload, guest_email, registered_user, stub_amocrm
from test_orders_api import (
    _build_pickup_payload, _create_ready_draft, _get_order, _update_order, sync_engine, variant_factory,
)


def _run(order_id):
    with Session(sync_engine) as db:
        return db.scalars(select(IntegrationRun).where(
            IntegrationRun.idempotency_key == auto._key(order_id))).one()


def _due(run_id):
    with Session(sync_engine) as db:
        db.get(IntegrationRun, run_id).next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()


@pytest.fixture
def checkout(client, registered_user, guest_email, variant_factory, stub_amocrm, monkeypatch):
    headers = registered_user["headers"]
    wake = AsyncMock(side_effect=ConnectionError("test Redis unavailable"))
    monkeypatch.setattr(jobs, "enqueue_integration_run", wake)
    monkeypatch.setattr(payments, "MOY_SKLAD_ORDER_SYNC_ENABLED", True)
    monkeypatch.setattr("src.app.services.orders.creation.draft.sync_order_to_moysklad_safe", AsyncMock())
    monkeypatch.setattr("src.integrations.moysklad.order_sync.states.MOY_SKLAD_ORDER_SYNC_ENABLED", False)
    monkeypatch.setattr(payment_attempt, "_local_deadlines", {})
    monkeypatch.setattr(payment_attempt, "get_cache_service", lambda: SimpleNamespace(client=None))
    async def export(db, *, order, user):
        order.moysklad_customerorder_id = uuid4()
        order.moysklad_invoiceout_id = uuid4()
        hold = order.checkout_snapshot["stock_reservation"]
        order.checkout_snapshot = {**order.checkout_snapshot, "stock_reservation": {
            **hold, "status": "exported", "remote_quantities": {"test-sku": 2}}}
        await db.commit()
        return SimpleNamespace(skipped_reason=None)
    exporter = AsyncMock(side_effect=export)
    monkeypatch.setattr(auto, "sync_order_to_moysklad", exporter)
    verify = AsyncMock()
    monkeypatch.setattr(payments, "_verify_sbp_documents", verify)
    invoice = AsyncMock(return_value={"InvoiceId": "test-invoice"})
    state = {"Result": {"PaymentStep": "Created", "Form3DS": '{"SbpQrCodeUrl":"https://example.test/pay"}'}}
    sbp = AsyncMock(return_value=state)
    monkeypatch.setattr(payments.intellectmoney, "create_invoice", invoice)
    monkeypatch.setattr(payments.intellectmoney, "sbp_payment", sbp)
    monkeypatch.setattr(payments.intellectmoney, "get_bank_card_payment_state", AsyncMock(return_value=state))
    monkeypatch.setattr("src.app.services.orders._resolve_payment_qr_image", AsyncMock(return_value=None))
    monkeypatch.setattr(payments, "_resolve_payment_qr_image", AsyncMock(return_value=None))

    def submit(source="draft", method="sbp", automatic=True):
        variant = variant_factory()["variant_id"]
        payload = {"payment_method": method, "automatic_checkout": automatic}
        if source == "guest":
            guest = _build_guest_order_payload(variant_id=variant, email=guest_email)
            response = client.post("/api/v1/guest/orders", json={**guest, **payload})
            if response.is_success:
                customer = response.json()
                return customer["order"]["id"], {"Authorization": f"Bearer {customer['access_token']}"}
        else:
            if source == "draft":
                payload["draft_id"] = _create_ready_draft(client, headers, variant)["id"]
            else:
                assert client.post("/api/v1/users/me/basket/items", headers=headers,
                                   json={"variant_id": variant, "quantity": 2}).is_success
                assert client.patch("/api/v1/users/me/basket/checkout", headers=headers, json={
                    "new_delivery_address": _build_pickup_payload(), "new_recipient": {
                        "name": "Test", "surname": "Buyer", "phone": "+79991234567", "email": "test@example.com"}}).is_success
            response = client.post("/api/v1/users/me/orders", json=payload, headers=headers)
            if response.is_success:
                return response.json()["id"], headers
        return response
    return SimpleNamespace(submit=submit, wake=wake, export=exporter, verify=verify, invoice=invoice, sbp=sbp)


@pytest.mark.parametrize("source,method", [("guest", "sbp"), ("draft", "sbp"), ("basket", "later")])
def test_order_commit_recovers_without_any_second_request(client, checkout, source, method, monkeypatch):
    oid, headers = checkout.submit(source, method)
    run = _run(oid)
    assert run.status == "queued" and run.input_json["prepare_order"]
    history_url = f"/api/v1/users/me/orders/{oid}"
    first = client.get(history_url, headers=headers).json()
    assert first["status_code"] == "processing" and first["status"] == "Оформляется"
    assert datetime.fromisoformat(first["checkout_snapshot"]["stock_reservation"]["expires_at"]) == run.started_at + timedelta(hours=1)
    checkout.export.assert_not_awaited()
    checkout.invoice.assert_not_awaited()
    checkout.wake.assert_awaited_once_with(run.id)

    # No app request after order creation. Recover the missing Redis delivery from SQL.
    recovered = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_integration_run", recovered)
    client.portal.call(jobs.recover_due_database_runs)
    recovered.assert_any_await(run.id)
    async def workers():
        await asyncio.gather(jobs.execute_integration_run(run.id), jobs.execute_integration_run(run.id))
    client.portal.call(workers)
    assert _run(oid).status == "success", _run(oid).error
    assert _run(oid).attempts == 1
    assert client.get(history_url, headers=headers).json()["status_code"] not in {"processing", "checkout_failed"}
    with Session(sync_engine) as db:
        notices = db.scalars(select(IntegrationRun).where(IntegrationRun.idempotency_key == f"app:checkout-notice:{run.id}:created")).all()
        assert len(notices) == 1
    checkout.export.assert_awaited_once()
    if method == "sbp":
        saved = _get_order(oid)
        assert saved.payment_invoice_id == saved.checkout_snapshot["sbp_ready_invoice_id"] == "test-invoice"
        checkout.invoice.assert_awaited_once()
        checkout.sbp.assert_awaited_once()
        assert checkout.invoice.await_args.kwargs["result_url"] == "https://example.test/api/v1/webhooks/intellectmoney"
    else:
        assert _get_order(oid).payment_provider == "manager"
        checkout.invoice.assert_not_awaited()
    legacy = client.post("/api/v1/payments/create", json={"order_id": oid}, headers=headers)
    assert legacy.is_success, legacy.text
    if method == "sbp":
        assert legacy.json()["qr_url"] == "https://example.test/pay"
        checkout.invoice.assert_awaited_once()
    else:
        assert legacy.json()["ms_reservation_confirmed"] and legacy.json()["amount_rubles"] > 0


@pytest.mark.parametrize("source", ["draft", "basket", "guest"])
def test_stage_failure_rolls_back_entire_order(checkout, source, monkeypatch):
    stage = auto.stage_checkout
    ids = []
    async def fail_after_insert(db, order, *args, **kwargs):
        ids.append((order.id, order.user_id, await stage(db, order, *args, **kwargs)))
        raise HTTPException(503, "injected before commit")
    monkeypatch.setattr(auto, "stage_checkout", fail_after_insert)
    assert checkout.submit(source).status_code == 503
    oid, uid, rid = ids[0]
    with Session(sync_engine) as db:
        assert db.get(Order, oid) is None and db.get(IntegrationRun, rid) is None
        if source == "guest":
            assert db.get(User, uid) is None
    checkout.wake.assert_not_awaited()


@pytest.mark.parametrize("change", ["paid", "canceled", "shipped", "method", "invoice", "ambiguous", "none"])
def test_delayed_worker_rechecks_intent(client, checkout, change):
    oid, headers = checkout.submit()
    rid = _run(oid).id
    checkout.verify.side_effect = payments.settlement_pending(seconds=78)
    client.portal.call(jobs.execute_integration_run, rid)
    run = _run(oid)
    assert run.status == "retrying" and run.next_attempt_at > datetime.now(timezone.utc) + timedelta(seconds=70)
    client.portal.call(jobs.execute_integration_run, rid)
    assert _run(oid).attempts == 1
    for url in ("status", "create"):
        req = client.get if url == "status" else client.post
        key = "params" if url == "status" else "json"
        response = req(f"/api/v1/payments/{url}", headers=headers, **{key: {"order_id": oid}})
        assert response.status_code == 409 and response.json()["detail"]["code"] == "settlement_pending"
        result = req(f"/api/v1/payments/{url}", headers=headers, **{key: {"order_id": oid, "automatic_checkout": True}})
        assert result.is_success and result.json()["checkout_progress"] == "processing"
        assert result.json()["amount_rubles"] is None
    checkout.verify.side_effect = None
    payment_attempt._local_deadlines.clear()
    patches = {"paid": {"is_paid": True}, "canceled": {"is_canceled": True}, "shipped": {"is_shipped": True},
               "method": {"payment_method": "later"}, "invoice": {"payment_invoice_id": "different"},
               "ambiguous": {"payment_provider": "intellectmoney", "payment_status": "created"}, "none": {}}
    _update_order(oid, **patches[change])
    _due(rid)
    client.portal.call(jobs.execute_integration_run, rid)
    assert _run(oid).status == ("error" if change in {"ambiguous", "method", "invoice"} else "success")
    if change == "none":
        checkout.invoice.assert_awaited_once()
    else:
        checkout.invoice.assert_not_awaited()
    checkout.export.assert_awaited_once()


def test_lost_invoice_reply_and_replay_require_review(client, checkout):
    oid, headers = checkout.submit()
    run = _run(oid)
    checkout.invoice.side_effect = TimeoutError("invoice may exist")
    client.portal.call(jobs.execute_integration_run, run.id)
    assert _run(oid).status == "error" and _get_order(oid).payment_provider == "intellectmoney"
    async def replay():
        async with SessionLocal() as db:
            with pytest.raises(HTTPException, match="reconciliation"):
                await auto.complete_checkout(db, oid, run.input_json)
    client.portal.call(replay)
    assert _run(oid).input_json["payment_submitted"]
    # Even resetting the order-side fields and replaying the original job
    # cannot authorize a second outgoing invoice.
    _update_order(oid, payment_provider=None, payment_status="draft")
    with Session(sync_engine) as db:
        db.get(IntegrationRun, run.id).status = "queued"
        db.commit()
    client.portal.call(jobs.execute_integration_run, run.id)
    assert _run(oid).status == "error"
    for automatic in (False, True):
        r = client.post("/api/v1/payments/create", headers=headers, json={"order_id": oid, "automatic_checkout": automatic})
        if automatic:
            assert r.json()["checkout_progress"] == "needs_review" and not r.json()["can_retry"]
        else:
            assert r.status_code == 409 and r.json()["detail"]["code"] == "checkout_needs_review"
    checkout.invoice.assert_awaited_once()
    checkout.sbp.assert_not_awaited()


@pytest.mark.parametrize("patch", [
    {"is_canceled": True}, {"payment_method": "later"}, {"payment_invoice_id": "newer"},
    {"grand_total": 999}, {"payment_provider": "intellectmoney", "payment_status": "created"},
])
def test_change_during_slow_verification_prevents_provider_submission(client, checkout, patch):
    oid, _ = checkout.submit()
    async def verify(*_args):
        async with SessionLocal() as other:
            await other.execute(text("SET LOCAL lock_timeout = '2s'"))
            await other.execute(update(Order).where(Order.id == oid).values(**patch))
            await other.commit()
    checkout.verify.side_effect = verify
    client.portal.call(jobs.execute_integration_run, _run(oid).id)
    assert _run(oid).status == "error"
    fresh = _get_order(oid)
    assert all(getattr(fresh, key) == value for key, value in patch.items())
    checkout.invoice.assert_not_awaited()


def test_ambiguous_sbp_with_known_invoice_can_recover_qr_without_resubmission(client, checkout):
    oid, headers = checkout.submit()
    checkout.sbp.side_effect = TimeoutError("SBP accepted but response lost")
    client.portal.call(jobs.execute_integration_run, _run(oid).id)
    assert _run(oid).status == "retrying"
    assert _get_order(oid).payment_invoice_id == "test-invoice"
    _due(_run(oid).id)
    client.portal.call(jobs.execute_integration_run, _run(oid).id)
    assert _run(oid).status == "success"
    legacy = client.post("/api/v1/payments/create", json={"order_id": oid}, headers=headers)
    assert legacy.is_success and legacy.json()["qr_url"] == "https://example.test/pay"
    checkout.invoice.assert_awaited_once()
    checkout.sbp.assert_awaited_once()


def test_automatic_manager_ack_waits_for_handoff_legacy_keeps_its_contract(client, checkout):
    oid, headers = checkout.submit(method="later")
    run = _run(oid)
    with Session(sync_engine) as db:
        row = db.get(Order, oid)
        row.moysklad_customerorder_id = uuid4()
        row.checkout_snapshot = {**row.checkout_snapshot, "stock_reservation": {
            "status": "exported", "remote_quantities": {"test-sku": 2}},
            "settlement_payment": {"version": 1, "counterparty_id": str(uuid4()), "mode": "automatic",
                "status": "awaiting_invoice", "maximum_balance_rubles": "0", "gross_rubles": str(row.grand_total)}}
        job = db.get(IntegrationRun, run.id)
        job.input_json = {**job.input_json, "terms": auto._approved_terms(row)}
        job.status = "running"
        db.commit()
    for automatic in (True, False):
        res = client.post("/api/v1/payments/create", json={"order_id": oid, "automatic_checkout": automatic}, headers=headers)
        if automatic:
            assert res.is_success and res.json()["checkout_progress"] == "processing"
            continue
        assert res.is_success and res.json()["checkout_progress"] is None
        assert res.json()["ms_reservation_confirmed"] and res.json()["amount_rubles"] > 0
        assert not res.json()["awaiting_settlement"] and not res.json()["is_paid"]
    checkout.export.assert_not_awaited()
    checkout.invoice.assert_not_awaited()


def test_one_hour_deadline_preserves_concrete_safe_reason_and_one_notice(client, checkout, monkeypatch):
    oid, headers = checkout.submit(method="later")
    rid = _run(oid).id
    request = httpx.Request("GET", "https://api.moysklad.ru/api/remap/1.2/entity/country?token=private-example")
    checkout.export.side_effect = httpx.HTTPStatusError(f"429 {request.url}", request=request,
        response=httpx.Response(429, headers={"Retry-After": "7200"}))
    with Session(sync_engine) as db:
        run = db.get(IntegrationRun, rid)
        run.attempts, run.max_attempts = 14, 14
        run.started_at = datetime.now(timezone.utc) - timedelta(minutes=52)
        db.commit()
    client.portal.call(jobs.execute_integration_run, rid)
    run = _run(oid)
    assert run.attempts == 15 and run.status == "retrying"
    assert run.next_attempt_at == run.started_at + timedelta(hours=1)
    url = f"/api/v1/users/me/orders/{oid}"
    data = client.get(url, headers=headers).json()
    assert data["status_code"] == "processing"
    issue = data["checkout_issue"]
    assert issue["retrying"] and issue["code"] == "MS_429" and "страну" in issue["message"]
    def filtered(code):
        return {item["id"] for item in client.get("/api/v1/users/me/orders", headers=headers,
                                                 params={"status_code": code}).json()}
    assert oid in filtered("processing") and oid not in filtered("created")
    assert "private-example" not in str(data) and "https://" not in issue["message"]
    with Session(sync_engine) as db:
        run = db.get(IntegrationRun, rid)
        run.started_at -= timedelta(minutes=10)
        run.next_attempt_at = run.started_at + timedelta(hours=1)
        db.commit()
    client.portal.call(jobs.execute_integration_run, rid)
    client.portal.call(jobs.execute_integration_run, rid)
    assert checkout.export.await_count == 1
    data = client.get(url, headers=headers).json()
    assert data["status_code"] == "checkout_failed" and not data["checkout_issue"]["retrying"]
    assert data["checkout_issue"]["code"] == "MS_429"
    assert oid in filtered("checkout_failed") and oid not in filtered("processing")
    with Session(sync_engine) as db:
        notice = db.scalars(select(IntegrationRun).where(
            IntegrationRun.idempotency_key == f"app:checkout-notice:{rid}:checkout_failed")).one()
        notice_id = notice.id
    push = AsyncMock(return_value=True)
    monkeypatch.setattr("src.app.services.push_notifications.send_push_to_user", push)
    client.portal.call(jobs.execute_integration_run, notice_id)
    client.portal.call(jobs.execute_integration_run, notice_id)
    push.assert_awaited_once()
    assert push.await_args.kwargs["data"]["order_id"] == oid


def test_missing_qr_retries_existing_invoice_without_another_sbp_submission(client, checkout, monkeypatch):
    oid, headers = checkout.submit()
    rid = _run(oid).id
    empty = {"Result": {"PaymentStep": "Created"}}
    checkout.sbp.return_value = empty
    get_state = AsyncMock(return_value=empty)
    monkeypatch.setattr(payments.intellectmoney, "get_bank_card_payment_state", get_state)
    client.portal.call(jobs.execute_integration_run, rid)
    assert _run(oid).status == "retrying"
    assert _get_order(oid).payment_invoice_id == "test-invoice"
    get_state.return_value = {"Result":{"PaymentStep":"Created", "Form3DS":'{"SbpQrCodeUrl":"https://example.test/qr"}'}}
    assert _get_order(oid).checkout_snapshot.get("sbp_ready_invoice_id") is None
    _due(rid)
    client.portal.call(jobs.execute_integration_run, rid)
    assert _run(oid).status == "success", _run(oid).error
    checkout.invoice.assert_awaited_once()
    checkout.sbp.assert_awaited_once()
    assert _get_order(oid).checkout_snapshot["sbp_ready_invoice_id"] == "test-invoice"


def test_no_push_uses_only_the_verified_buyer_email(client, checkout, monkeypatch):
    oid, _ = checkout.submit(method="later")
    from src.app.services.orders.checkout_lifecycle import notify_result
    monkeypatch.setattr("src.app.services.push_notifications.send_push_to_user", AsyncMock(return_value=False))
    mail = AsyncMock()
    monkeypatch.setattr("src.app.services.email_verification.send_checkout_result_email", mail)
    async def notify():
        async with SessionLocal() as db:
            return await notify_result(db, oid, "created")
    result = client.portal.call(notify)
    assert result["channel"] == "email"
    mail.assert_awaited_once()
    assert _get_order(oid).order_code in mail.await_args.kwargs["subject"]
    guest, _ = checkout.submit(source="guest")
    oid = guest
    assert client.portal.call(notify)["reason"] == "no_verified_channel"
    mail.assert_awaited_once()


def test_legacy_post_stages_missing_export_but_get_does_not(client, checkout):
    oid, headers = checkout.submit(automatic=False)
    client.get("/api/v1/payments/status", params={"order_id": oid}, headers=headers)
    with Session(sync_engine) as db:
        assert db.scalar(select(IntegrationRun.id).where(IntegrationRun.idempotency_key == auto._key(oid))) is None
    for _ in range(2):
        r = client.post("/api/v1/payments/create", json={"order_id": oid}, headers=headers)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "settlement_pending"
    client.portal.call(jobs.execute_integration_run, _run(oid).id)
    assert _run(oid).status == "success", _run(oid).error
    checkout.invoice.assert_awaited_once()
    checkout.export.assert_awaited_once()
