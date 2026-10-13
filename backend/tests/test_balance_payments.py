import asyncio
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from src.integrations.moysklad import balance_payments as payments
from src.integrations.moysklad.client import MoySkladClient
from src.app.services.benefits import loyalty, settlement, service as benefits
from src.app.services.benefits.moysklad_bonus import MoySkladBonusWallet
from src.app.services.referrals import wallet_sync
from src.app.services.notifications import core as notifications
from src.app.modules.users.me.schemas.benefits import BenefitCheckRead
from src.database.models import User

CID, TEMPLATE, PAYMENT, STATE, CURRENCY, ORG, ATTR, VALUE = [UUID(int=i) for i in range(1, 9)]


@pytest.fixture
def client(monkeypatch):
    client = MoySkladClient(token="test", base_url="https://example.test/api")
    ref = lambda path, kind: client._meta_payload(href=client.base_url + path, entity_type=kind)
    template = {
        "id": str(TEMPLATE), "applicable": True,
        "organization": ref(f"/entity/organization/{ORG}", "organization"),
        "state": ref(f"/entity/paymentin/metadata/states/{STATE}", "state"),
        "rate": {"currency": ref(f"/entity/currency/{CURRENCY}", "currency")},
        "attributes": [
            {**ref(f"/entity/paymentin/metadata/attributes/{ATTR}", "attributemetadata"), "name": "Тип платежа",
             "value": {**ref(f"/entity/customentity/{ATTR}/{VALUE}", "customentity"), "name": "Бонусная"}},
            {**ref(f"/entity/paymentin/metadata/attributes/{VALUE}", "attributemetadata"), "name": "Бонусов начислено", "value": 100},
            {"name": "Отгрузка с начислением", "value": "DO NOT COPY"},
        ],
    }
    existing = AsyncMock(return_value=None)
    monkeypatch.setattr(client, "_find_entity_by_external_code", existing)
    monkeypatch.setattr(client, "_get_entity_by_id", AsyncMock(return_value=template))
    monkeypatch.setattr(client, "get_all", AsyncMock(return_value=[]))
    state = {"name": "Бонусная (Накопительная)"}
    currency = {"isoCode": "B.RUB", "rate": 1, "multiplicity": 1}

    async def get(url):
        return httpx.Response(200, request=httpx.Request("GET", url),
            json=state if str(STATE) in url else currency)

    http = SimpleNamespace(get=AsyncMock(side_effect=get))
    monkeypatch.setattr(client, "client", AsyncMock(return_value=http))

    async def create(kind, payload):
        return {"id": str(PAYMENT), **deepcopy(payload)}

    monkeypatch.setattr(client, "_create_entity", AsyncMock(side_effect=create))
    monkeypatch.setattr(payments, "MOY_SKLAD_BONUS_PAYMENT_TEMPLATE_ID", str(TEMPLATE))
    return SimpleNamespace(client=client, template=template, state=state, currency=currency, http=http)


def post(env, amount=Decimal(1000)):
    return asyncio.run(payments.create_bonus_balance_payment(env.client, counterparty_id=CID,
        amount=amount, external_code="test-welcome-1", description="Welcome reward #1", payment_purpose="App registration #1", is_welcome=True))


def test_payment_uses_accounting_fields_and_ruble_minor_units(client):
    result = post(client)
    kind, payload = client.client._create_entity.await_args.args
    assert kind == "paymentin"
    assert payload["sum"] == 100000 and payload["vatSum"] == 0
    assert payload["applicable"] is True and "operations" not in payload
    assert payload["paymentPurpose"] == "App registration #1"
    assert payload["attributes"][1]["value"] == 1000
    assert len(payload["attributes"]) == 2
    assert "DO NOT COPY" not in str(payload)
    assert UUID(payload["syncId"])
    assert result["id"] == str(PAYMENT)


def test_repeated_credit_returns_existing_payment(client):
    first = post(client)
    client.client._find_entity_by_external_code.return_value = first
    second = post(client)
    assert second["id"] == first["id"]
    client.client._create_entity.assert_awaited_once()


def test_previously_credited_manual_welcome_payment_requires_review(client):
    client.client.get_all.return_value = [{"sum": 100000, "applicable": True,
        "description": "Приветственное начисление за регистрацию", "externalCode": "manual"}]
    with pytest.raises(RuntimeError, match="reconciliation"):
        post(client)
    client.client._create_entity.assert_not_awaited()


def test_timeout_after_remote_create_recovers_same_payment(client):
    saved = post(client)
    client.client._create_entity.reset_mock()
    client.client._create_entity.side_effect = httpx.ReadTimeout("lost response")
    client.client._find_entity_by_external_code.side_effect = [None, saved]
    assert post(client)["id"] == str(PAYMENT)
    client.client._create_entity.assert_awaited_once()


@pytest.mark.parametrize("field,value", [
    ("sum", 100), ("vatSum", 100), ("applicable", False),
    ("externalCode", "different"), ("operations", [{"sum": 100}]),
    ("agent", {}), ("organization", {}), ("state", {}), ("rate", {}), ("attributes", []),
])
def test_conflicting_existing_payment_is_never_reused_or_overwritten(client, field, value):
    existing = post(client)
    existing[field] = value
    client.client._find_entity_by_external_code.return_value = existing
    client.client._create_entity.reset_mock()
    with pytest.raises(RuntimeError):
        post(client)
    client.client._create_entity.assert_not_awaited()


@pytest.mark.parametrize("amount", [Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_invalid_amount_cannot_create_payment(client, amount):
    with pytest.raises(ValueError):
        post(client, amount)
    client.client._create_entity.assert_not_awaited()


@pytest.mark.parametrize("field,value", [("isoCode", "RUB"), ("rate", 2), ("multiplicity", 100)])
def test_wrong_currency_blocks_posting(client, field, value):
    client.currency[field] = value
    with pytest.raises(RuntimeError, match="currency"):
        post(client)
    client.client._create_entity.assert_not_awaited()


def test_wrong_status_blocks_posting(client):
    client.state["name"] = "Стандарт"
    with pytest.raises(RuntimeError, match="state"):
        post(client)
    client.client._create_entity.assert_not_awaited()


def test_template_cannot_forward_authorization_to_other_host(client):
    client.template["state"]["meta"]["href"] = f"https://other.test/entity/paymentin/metadata/states/{STATE}"
    with pytest.raises(RuntimeError, match="reference"):
        post(client)
    client.http.get.assert_not_awaited()


@pytest.mark.parametrize("kind", ["welcome", "review_text", "review_photo"])
def test_app_credit_records_payment_reference_and_has_no_expiry(monkeypatch, kind):
    monkeypatch.setattr(loyalty, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    invalidate = AsyncMock()
    monkeypatch.setattr(settlement, "invalidate_account_settlement", invalidate)
    user = SimpleNamespace(id=1, moysklad_counterparty_id=CID)
    credit = SimpleNamespace(id=1, user_id=1, source_kind=kind, points=1000,
        status="failed", idempotency_key="welcome:user:1", expires_at="old", sync_error="old")
    db = SimpleNamespace(get=AsyncMock(return_value=user), commit=AsyncMock(), rollback=AsyncMock())
    post_payment = AsyncMock(return_value={"id": str(PAYMENT)})
    monkeypatch.setattr(loyalty, "create_bonus_balance_payment", post_payment)
    client = SimpleNamespace(is_configured=lambda: True)
    assert asyncio.run(loyalty.sync_loyalty_bonus_credit(db, credit=credit, client=client)) is True
    assert credit.status == "applied" and credit.moysklad_paymentin_id == PAYMENT
    assert credit.expires_at is None and credit.sync_error is None
    assert post_payment.await_args.kwargs["amount"] == 1000
    invalidate.assert_awaited_once_with(CID)
    assert asyncio.run(loyalty.sync_loyalty_bonus_credit(db, credit=credit, client=client)) is True
    post_payment.assert_awaited_once()


def test_historical_native_credit_is_not_migrated_automatically(monkeypatch):
    monkeypatch.setattr(loyalty, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    credit = SimpleNamespace(id=1, status="applied")
    db = SimpleNamespace(get=AsyncMock())
    assert asyncio.run(loyalty.sync_loyalty_bonus_credit(db, credit=credit)) is True
    db.get.assert_not_awaited()


def test_settlement_mode_does_not_duplicate_cashback_or_expire_money(monkeypatch):
    monkeypatch.setattr(loyalty, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    db = SimpleNamespace(execute=AsyncMock())
    assert asyncio.run(loyalty.grant_order_cashback_safe(db, order=None, user=None)) is None
    assert asyncio.run(loyalty.expire_loyalty_bonus_credits(db)) == {"processed": 0, "expired": 0, "failed": 0}
    assert asyncio.run(loyalty.reverse_loyalty_bonus_credit(db, credit=None)) is False
    assert asyncio.run(loyalty.loyalty_bonus_expiration_summary(db, user_id=1))["next_expires_at"] is None
    db.execute.assert_not_awaited()


def test_other_native_mutation_jobs_are_disabled_in_settlement_mode(monkeypatch):
    monkeypatch.setattr(wallet_sync, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(notifications, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    db = SimpleNamespace(execute=AsyncMock())
    assert asyncio.run(wallet_sync.sync_referral_accrual_to_bonus_wallet(db, accrual=None)) == "not_applicable"
    assert asyncio.run(wallet_sync.sync_approved_referral_accruals_to_bonus_wallet(db))["processed"] == 0
    assert asyncio.run(notifications.process_bonus_expiry_notifications(db)) == 0
    db.execute.assert_not_awaited()


def test_pending_rewards_are_not_available_checkout_money(monkeypatch):
    monkeypatch.setattr(benefits, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    monkeypatch.setattr(benefits, "_resolve_subtotals", AsyncMock(return_value=(Decimal(9180), Decimal(9180), "explicit")))
    monkeypatch.setattr(benefits, "ensure_default_reward_program", AsyncMock(return_value=SimpleNamespace(id=1, reward_program="bonus")))
    monkeypatch.setattr(benefits, "refresh_profile_discount", lambda *args, **kwargs: None)
    monkeypatch.setattr(benefits, "reward_program_selection_required", lambda profile: False)
    monkeypatch.setattr(benefits, "get_user_moysklad_bonus_wallet", AsyncMock(return_value=MoySkladBonusWallet()))
    monkeypatch.setattr(benefits, "pending_loyalty_bonus_points", AsyncMock(return_value=1000))
    user = SimpleNamespace(id=1, promo_code=None)
    result = asyncio.run(benefits.resolve_benefits_for_user(SimpleNamespace(), user=user, use_bonus_rubles=True))
    assert result["bonus_pending_points"] == 1000
    assert result["bonus_balance_points"] == 0 and result["bonus_balance_rubles"] == 0
    assert result["bonus_option"] is None and result["total_after_discounts"] == 9180
    assert result["cashback_expires_in_days"] == 0
    assert BenefitCheckRead.model_validate(result).bonus_applied_rubles == 0


def test_failed_post_is_retained_for_idempotent_retry(monkeypatch):
    monkeypatch.setattr(loyalty, "LOYALTY_USE_SETTLEMENT_BALANCE", True)
    user = SimpleNamespace(id=1, moysklad_counterparty_id=CID)
    credit = SimpleNamespace(id=1, user_id=1, source_kind="welcome", points=1000,
        status="pending", idempotency_key="welcome:user:1", moysklad_paymentin_id=None)
    db = SimpleNamespace(get=AsyncMock(side_effect=lambda model, identifier: user if model is User else credit),
        commit=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(loyalty, "create_bonus_balance_payment", AsyncMock(side_effect=RuntimeError("retryable")))
    assert asyncio.run(loyalty.sync_loyalty_bonus_credit(db, credit=credit,
        client=SimpleNamespace(is_configured=lambda: True))) is False
    assert credit.status == "failed" and credit.sync_error == "retryable"
    assert credit.moysklad_paymentin_id is None
    db.rollback.assert_awaited_once()
