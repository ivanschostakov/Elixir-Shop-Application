from datetime import datetime, timezone
import os
import subprocess
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import src.app.modules.auth.dependencies as auth_dependencies
import src.app.modules.products.router as products_router_module
import src.app.services.orders.payments as order_payments
from src.app.main import app
from src.app.modules.admin.orders import ALLOWED_TRANSITIONS
from src.app.modules.admin.campaigns import _normalize_utm, _rate
from src.app.modules.admin.integrations import REQUIRED_ADMIN_PERMISSIONS, REQUIRED_ADMIN_ROUTES
from src.app.services.admin.analytics import analytics_csv, percent
from src.app.services.admin.jobs import get_worker_heartbeats, is_retryable_error, parse_job, record_worker_heartbeat, retry_delay_seconds
from src.app.services.admin.exports import _write_csv, _write_xlsx, normalize_export_payload
from src.app.services.admin.audiences import normalize_segment_filters
from src.app.services.admin.automation import default_order_automation_presets, normalize_order_rule_action, normalize_order_rule_conditions, preset_rule_name
from src.app.services.notifications.core import normalize_marketing_automation_settings
from src.app.modules.admin.schemas import AdminExportCreatePayload
from src.app.services.admin.permissions import ALL_PERMISSIONS
from src.app.services.admin.security import (
    create_admin_access_token,
    decode_admin_token,
    decrypt_totp_secret,
    encrypt_totp_secret,
    verify_totp,
)
from src.app.services.security import create_access_token
from src.database import get_db


def test_totp_matches_rfc_vector_and_rejects_invalid_code():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert verify_totp(secret, "287082", timestamp=59, window=0)
    assert not verify_totp(secret, "287083", timestamp=59, window=0)
    assert not verify_totp(secret, "not-a-code", timestamp=59, window=0)


def test_admin_access_token_has_isolated_audience_and_type():
    token = create_admin_access_token(user_id=42, session_id=7)
    payload = decode_admin_token(token, expected_type="admin_access")
    assert payload is not None
    assert payload["aud"] == "admin"
    assert payload["sub"] == "42"
    assert payload["sid"] == "7"
    assert decode_admin_token(token, expected_type="admin_challenge") is None


def test_totp_secret_encryption_round_trip():
    secret = "JBSWY3DPEHPK3PXP"
    encrypted = encrypt_totp_secret(secret)
    assert encrypted != secret
    assert decrypt_totp_secret(encrypted) == secret
    assert decrypt_totp_secret("invalid") is None


def test_order_transitions_are_explicit_and_terminal():
    assert "paid" in ALLOWED_TRANSITIONS["invoice_sent"]
    assert "delivered" in ALLOWED_TRANSITIONS["sent"]
    assert ALLOWED_TRANSITIONS["canceled"] == frozenset()


def test_admin_job_retry_policy_is_bounded_and_rejects_permanent_errors():
    assert [retry_delay_seconds(attempt) for attempt in (1, 2, 3, 10)] == [5, 10, 20, 300]
    assert is_retryable_error(RuntimeError("network unavailable"))
    assert is_retryable_error(HTTPException(status_code=502, detail="provider unavailable"))
    assert not is_retryable_error(HTTPException(status_code=409, detail="missing order data"))


def test_admin_job_payload_and_recovery_permission_are_explicit():
    assert parse_job('{"run_id":42}') == 42
    assert parse_job('{"run_id":0}') is None
    assert parse_job("invalid") is None
    assert "orders.recover" in ALL_PERMISSIONS
    assert "exports.read" in ALL_PERMISSIONS
    assert {"tasks.read", "tasks.manage", "segments.read", "segments.manage", "campaigns.read", "campaigns.manage", "campaigns.send"}.issubset(ALL_PERMISSIONS)
    assert {"automation.read", "automation.manage", "sla.read", "sla.manage", "alerts.read", "alerts.manage"}.issubset(ALL_PERMISSIONS)


def test_customer_segment_filters_are_strict_and_allow_explicit_activity_scope():
    normalized = normalize_segment_filters({"min_orders": 2, "has_push_token": True})
    assert normalized["version"] == 2
    assert {"field": "order_count", "operator": "gte", "value": 2} in normalized["conditions"]
    assert {"field": "push_available", "operator": "eq", "value": True} in normalized["conditions"]
    assert all(item["field"] != "is_active" for item in normalized["conditions"])
    with pytest.raises((ValidationError, ValueError)):
        normalize_segment_filters({"unknown_filter": True})


def test_crm_and_campaign_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/admin/tasks" in paths
    assert "/api/v1/admin/segments/preview" in paths
    assert "/api/v1/admin/segments/{segment_id}/snapshot" in paths
    assert "/api/v1/admin/segments/{segment_id}/customers" in paths
    assert "/api/v1/admin/segments/{segment_id}/history" in paths
    assert "/api/v1/admin/campaign-templates" in paths
    assert "/api/v1/admin/campaigns/preview" in paths
    assert "/api/v1/admin/campaigns/{campaign_id}/launch" in paths
    assert "/api/v1/admin/campaigns/{campaign_id}/metrics" in paths
    assert "/api/v1/admin/campaigns/{campaign_id}/recipients" in paths
    assert "/api/v1/admin/automations/{automation_id}" in paths
    assert "/api/v1/admin/referrals/summary" in paths
    assert "/api/v1/admin/order-automation-rules/{rule_id}/run" in paths
    assert "/api/v1/admin/order-automation-rules/presets" in paths
    assert "/api/v1/admin/order-automation-rules/{rule_id}/preview" in paths
    assert "/api/v1/admin/sla-summary" in paths
    assert "/api/v1/admin/alerts/{alert_id}/resolve" in paths
    assert "/api/v1/admin/dashboard/preferences" in paths
    assert "/api/v1/admin/integrations/production-readiness" in paths
    assert "/api/v1/admin/analytics" in paths
    assert "/api/v1/admin/analytics/{section}.csv" in paths
    assert not (REQUIRED_ADMIN_ROUTES - paths)
    assert REQUIRED_ADMIN_PERMISSIONS.issubset(ALL_PERMISSIONS)


def test_order_automation_rule_payloads_are_strict_and_safe():
    conditions = normalize_order_rule_conditions({
        "status_codes": ["paid", "packaged"],
        "payment_statuses": [" paid ", "paid"],
        "min_age_minutes": 30,
        "missing_delivery": True,
    })
    assert conditions["status_codes"] == ["paid", "packaged"]
    assert conditions["payment_statuses"] == ["paid"]
    assert conditions["min_age_minutes"] == 30
    with pytest.raises(ValidationError):
        normalize_order_rule_conditions({"min_age_minutes": 1, "unknown": True})
    action = normalize_order_rule_action({"kind": "push_customer", "title": "Order", "body": "Ready", "deep_link": "/orders"})
    assert action["deep_link"] == "/orders"
    with pytest.raises(ValidationError):
        normalize_order_rule_action({"kind": "push_customer", "title": "Order", "body": "Ready", "deep_link": "https://example.com"})


def test_order_automation_presets_are_disabled_task_templates():
    presets = default_order_automation_presets(assignee_user_id=7)
    assert len(presets) >= 4
    assert len({preset["code"] for preset in presets}) == len(presets)
    for preset in presets:
        assert preset_rule_name(preset).startswith("[Preset] ")
        assert preset["action_json"]["kind"] == "create_task"
        assert preset["action_json"]["assignee_user_id"] == 7
        assert normalize_order_rule_conditions(preset["conditions_json"])
        assert normalize_order_rule_action(preset["action_json"])


def test_trigger_campaign_settings_keep_defaults_and_validate_intervals():
    defaults = normalize_marketing_automation_settings("abandoned_cart", {})
    assert defaults["after_hours"] == 24
    assert defaults["cooldown_hours"] == 24
    custom = normalize_marketing_automation_settings("review_reminder", {"after_days": 14})
    assert custom["after_days"] == 14
    assert custom["title"] == "Поделитесь отзывом"
    with pytest.raises(ValidationError):
        normalize_marketing_automation_settings("review_reminder", {"after_days": 0})


def test_campaign_marketing_payload_helpers_are_strict():
    assert _normalize_utm({"SOURCE": " admin ", "campaign": " summer "}) == {"source": "admin", "campaign": "summer"}
    assert str(_rate(1, 4)) == "25.00"
    with pytest.raises(HTTPException):
        _normalize_utm({"redirect": "https://example.com"})


def test_admin_analytics_helpers_escape_csv_and_calculate_percent():
    assert str(percent(1, 3)) == "33.33"
    assert str(percent(1, 0)) == "0.00"
    snapshot = {"sales": {"trend": [{"date": "2026-07-23", "revenue": "=100", "orders": 2}]}}
    csv_payload = analytics_csv("sales", snapshot).decode("utf-8-sig")
    assert "'=100" in csv_payload


def test_admin_export_payload_rejects_unknown_columns_and_filters():
    base = {
        "resource": "orders",
        "format": "csv",
        "columns": ["order_code", "status"],
        "filters": {"status_code": "paid"},
        "selected_ids": [4, 4, 9],
        "locale": "ru",
        "idempotency_key": "export-test-1",
    }
    normalized = normalize_export_payload(AdminExportCreatePayload.model_validate(base))
    assert normalized["selected_ids"] == [4, 9]

    with pytest.raises(ValueError, match="Unsupported export columns"):
        normalize_export_payload(AdminExportCreatePayload.model_validate({**base, "columns": ["password"]}))
    with pytest.raises(ValueError, match="Unsupported export filters"):
        normalize_export_payload(AdminExportCreatePayload.model_validate({**base, "filters": {"admin": True}}))


def test_admin_exports_escape_formulas_and_create_valid_xlsx(tmp_path):
    csv_path = tmp_path / "orders.csv"
    _write_csv(csv_path, ["Order"], [["=1+1"], [" safe"]])
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    assert "'=1+1" in csv_text

    xlsx_path = tmp_path / "orders.xlsx"
    _write_xlsx(xlsx_path, ["Order", "Total"], [["A-1", 1250]])
    with ZipFile(xlsx_path) as workbook:
        assert "xl/workbook.xml" in workbook.namelist()
        sheet = workbook.read("xl/worksheets/sheet1.xml").decode()
    assert "A-1" in sheet
    assert "1250" in sheet


def test_admin_worker_supports_cold_import():
    environment = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-c", "import src.workers.admin_jobs"],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    automation_result = subprocess.run(
        [sys.executable, "-c", "import src.workers.admin_automation"],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert automation_result.returncode == 0, automation_result.stderr
    assert callable(record_worker_heartbeat)
    assert callable(get_worker_heartbeats)


@pytest.mark.anyio
async def test_admin_payment_recheck_uses_provider_result(monkeypatch: pytest.MonkeyPatch):
    order = SimpleNamespace(
        id=17,
        is_paid=False,
        payment_status="pending",
        payment_method="sbp",
        payment_invoice_id="invoice-17",
    )

    class FakeIntellectMoney:
        async def get_bank_card_payment_state(self, *, invoice_id: str):
            assert invoice_id == "invoice-17"
            return {"Result": {"PaymentStatus": 5}}

        @staticmethod
        def parse_payment_state(payload):
            return {"payment_step": "OK", "qr_url": None, "qr_image": None}

    async def fake_reconcile(session, current_order=None, **kwargs):
        current_order = current_order or kwargs.pop("order")
        assert current_order is order
        assert kwargs["payment_status_code"] == 5
        current_order.payment_status = "paid"
        current_order.is_paid = True
        return current_order

    monkeypatch.setattr(order_payments, "intellectmoney", FakeIntellectMoney())
    monkeypatch.setattr(order_payments, "reconcile_sbp_payment", fake_reconcile)
    result = await order_payments.recheck_payment_status_for_admin(object(), order=order)
    assert result["previous_payment_status"] == "pending"
    assert result["payment_status"] == "paid"
    assert result["is_paid"] is True


def test_admin_endpoint_requires_admin_bearer_token(client: TestClient):
    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_mobile_access_token_cannot_use_admin_session(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_session(*args, **kwargs):
        return SimpleNamespace(
            id=7,
            user_id=42,
            purpose="admin",
            revoked_at=None,
            expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(auth_dependencies, "get_user_session_by_id", fake_get_session)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(user_id=42, session_id=7),
    )
    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(credentials=credentials, db=object())
    assert error.value.status_code == 401


def test_guest_can_submit_review_for_moderation(monkeypatch: pytest.MonkeyPatch):
    now = datetime.now(timezone.utc)

    class FakeDb:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def fake_get_db():
        yield FakeDb()

    async def fake_get_product_by_id(*args, **kwargs):
        return object()

    async def fake_create_product_review(*args, user_id, product_id, data, **kwargs):
        assert user_id is None
        assert product_id == 91
        assert data.guest_name == "Гость"
        return type("CreatedReview", (), {"id": 501})()

    async def fake_get_review_by_id(*args, **kwargs):
        return object()

    async def fake_rate_limit(*args, **kwargs):
        return None

    async def fake_bump_review_cache_namespaces():
        return None

    async def fake_analyze_review_submission(*args, **kwargs):
        return {
            "submitter_ip": "127.0.0.1",
            "duplicate_group_key": "guest-review-key",
            "spam_score": 0,
            "profanity_flag": False,
            "duplicate_flag": False,
            "suspicious_ip_flag": False,
            "moderation_flags": {},
        }

    def fake_serialize_review(*args, **kwargs):
        return {
            "id": 501,
            "author_username": "Гость",
            "product_id": 91,
            "value": 5,
            "text": "Отличный товар",
            "answer": None,
            "attachments": [],
            "likes": 0,
            "dislikes": 0,
            "moderated": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(products_router_module, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(products_router_module, "create_product_review", fake_create_product_review)
    monkeypatch.setattr(products_router_module, "get_review_by_id", fake_get_review_by_id)
    monkeypatch.setattr(products_router_module, "enforce_rate_limit", fake_rate_limit)
    monkeypatch.setattr(products_router_module, "analyze_review_submission", fake_analyze_review_submission)
    monkeypatch.setattr(products_router_module, "_bump_review_cache_namespaces", fake_bump_review_cache_namespaces)
    monkeypatch.setattr(products_router_module, "serialize_review", fake_serialize_review)

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/products/91/reviews",
                data={"value": "5", "text": "Отличный товар"},
            )
        assert response.status_code == 201, response.text
        assert response.json()["moderated"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
