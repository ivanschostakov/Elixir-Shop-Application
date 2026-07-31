import json
import asyncio
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from src.app.services.referrals.bitrix_sync import refresh_assigned_referrer_promo
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError


TOKEN = "a" * 64


def test_lookup_uses_server_token_and_returns_data(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Elixir-Promo-Token"] == TOKEN
        assert json.loads(request.content) == {"action": "lookup", "promo": "TEST"}
        return httpx.Response(
            200,
            json={"ok": True, "action": "lookup", "data": {"promo": "TEST", "discount_id": 24}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    assert asyncio.run(client.lookup("TEST")) == {"promo": "TEST", "discount_id": 24}


def test_error_preserves_russian_and_english_messages(monkeypatch):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "ok": False,
                "error": "promo_not_found",
                "message_ru": "Промокод не найден.",
                "message_en": "Promo code was not found.",
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )

    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    with pytest.raises(BitrixPromoError) as raised:
        asyncio.run(client.lookup("MISSING"))

    assert raised.value.status_code == 404
    assert raised.value.code == "promo_not_found"
    assert raised.value.message_ru == "Промокод не найден."
    assert raised.value.message_en == "Promo code was not found."


def test_quote_supports_email_user_context(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "quote",
            "promo": "TEST",
            "items": [{"product_system_id": "product-1", "quantity": 1}],
            "user_email": "customer@example.com",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": {"promo": "TEST", "user_context": "matched_by_email"}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(
        client.quote(
            promo="TEST",
            items=[{"product_system_id": "product-1", "quantity": 1}],
            user_email="customer@example.com",
        )
    )
    assert result["user_context"] == "matched_by_email"


@pytest.mark.parametrize(
    ("method_name", "expected_payload"),
    [
        (
            "context",
            {
                "action": "context",
                "promo": "REFERRER",
                "user_email": "customer@example.com",
            },
        ),
        (
            "attach_referrer",
            {
                "action": "attach_referrer",
                "promo": "REFERRER",
                "user_email": "customer@example.com",
            },
        ),
    ],
)
def test_user_promo_actions_include_customer_context(monkeypatch, method_name, expected_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == expected_payload
        return httpx.Response(
            200,
            json={"ok": True, "data": {"user_context": "matched_by_email"}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    method = getattr(client, method_name)
    result = asyncio.run(
        method(
            promo="REFERRER",
            user_email="customer@example.com",
        )
    )
    assert result["user_context"] == "matched_by_email"


def test_detach_referrer_includes_customer_context(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "detach_referrer",
            "user_email": "customer@example.com",
        }
        return httpx.Response(200, json={"ok": True, "data": {"outcome": "detached"}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(client.detach_referrer(user_email="customer@example.com"))
    assert result["outcome"] == "detached"


def test_profile_uses_customer_context_without_a_promo(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "profile",
            "user_email": "customer@example.com",
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "user_context": "matched_by_email",
                    "program_profile": {"referrer_promo": "REFERRER"},
                },
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)

    result = asyncio.run(client.profile(user_email="customer@example.com"))

    assert result["program_profile"]["referrer_promo"] == "REFERRER"


@pytest.mark.parametrize(
    ("current_promo", "website_promo", "expected_total"),
    [
        ("OLD", "CURRENT", Decimal("50000.00")),
        ("STALE", None, Decimal("0.00")),
    ],
)
def test_profile_refresh_updates_or_clears_local_referrer_promo(
    monkeypatch,
    current_promo,
    website_promo,
    expected_total,
):
    class FakeDb:
        def __init__(self):
            self.flushed = False

        async def flush(self):
            self.flushed = True

    class FakeClient:
        async def profile(self, *, bitrix_user_id=None, user_email):
            assert bitrix_user_id is None
            assert user_email == "customer@example.com"
            return {
                "program_profile": {
                    "referrer_promo": website_promo,
                    "order_sum": {"amount": 50000},
                },
            }

    db = FakeDb()
    user = SimpleNamespace(
        id=17,
        email="customer@example.com",
        promo_code=current_promo,
    )
    profile = SimpleNamespace(
        bitrix_user_id=None,
        bitrix_sync_status="pending",
        bitrix_synced_at=None,
        bitrix_sync_error=None,
        partner_unlocked_at=None,
        referral_discount_base_total=Decimal("0.00"),
        current_discount_percent=Decimal("0.00"),
        reward_program_snapshot={},
    )
    async def ensure_unified(_db, *, user):
        return profile

    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.bitrix_promo_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.ensure_unified_reward_program",
        ensure_unified,
    )

    program_profile = asyncio.run(
        refresh_assigned_referrer_promo(db, user=user, client=FakeClient())
    )

    assert program_profile["order_sum"]["amount"] == 50000
    assert user.promo_code == website_promo
    assert profile.referral_discount_base_total == expected_total
    assert db.flushed is True


def test_profile_refresh_preserves_configured_firm_promo(monkeypatch):
    class FakeDb:
        async def flush(self):
            return None

    class FakeClient:
        async def profile(self, *, bitrix_user_id=None, user_email):
            return {
                "user_id": 77,
                "program_profile": {
                    "referrer_promo": None,
                    "firm_promo_codes": ["Elixir"],
                    "order_sum": {"amount": 12500},
                },
            }

    profile = SimpleNamespace(
        bitrix_user_id=None,
        bitrix_sync_status="pending",
        bitrix_synced_at=None,
        bitrix_sync_error=None,
        partner_unlocked_at=None,
        referral_discount_base_total=Decimal("0.00"),
        current_discount_percent=Decimal("0.00"),
        reward_program_snapshot={},
    )
    user = SimpleNamespace(
        id=17,
        email="customer@example.com",
        promo_code="ELIXIR",
    )

    async def ensure_unified(_db, *, user):
        return profile

    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.bitrix_promo_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.app.services.referrals.bitrix_sync.ensure_unified_reward_program",
        ensure_unified,
    )

    program_profile = asyncio.run(
        refresh_assigned_referrer_promo(
            FakeDb(),
            user=user,
            client=FakeClient(),
        )
    )

    assert program_profile["firm_promo_codes"] == ["Elixir"]
    assert user.promo_code == "ELIXIR"
    assert profile.bitrix_user_id == 77


@pytest.mark.parametrize(
    ("method_name", "action", "response_data"),
    [
        (
            "quote_referral_accrual",
            "quote_referral_accrual",
            {"storage": "app", "bitrix_writes": False, "accruals": []},
        ),
        (
            "record_paid_purchase",
            "record_paid_purchase",
            {"outcome": "recorded", "purchase": {"id": 17}},
        ),
    ],
)
def test_paid_order_actions_send_idempotent_order_identity(
    monkeypatch,
    method_name,
    action,
    response_data,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": action,
            "external_order_id": "EP-ORDER01",
            "user_email": "customer@example.com",
            "promo": "REFERRER",
            "amount": "12500.00",
            "currency": "RUB",
            "paid_at": "2026-07-28T12:00:00+00:00",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": response_data},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    method = getattr(client, method_name)
    result = asyncio.run(
        method(
            external_order_id="EP-ORDER01",
            user_email="customer@example.com",
            promo="REFERRER",
            amount="12500.00",
            currency="RUB",
            paid_at="2026-07-28T12:00:00+00:00",
        )
    )
    assert result == response_data


def test_referral_eligibility_uses_bitrix_user_identity(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "referral_eligibility",
            "period": "2026-06",
            "user_id": 396,
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "status": "approved",
                    "period": "2026-06",
                    "user_id": 396,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(
        client.referral_eligibility(
            period="2026-06",
            bitrix_user_id=396,
        )
    )
    assert result["status"] == "approved"


def test_paid_purchase_without_partner_promo_omits_promo_field(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "record_paid_purchase",
            "external_order_id": "EP-NOPROMO",
            "user_email": "customer@example.com",
            "amount": "5510.00",
            "currency": "RUB",
            "paid_at": "2026-07-26T12:00:00+00:00",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": {"outcome": "recorded", "accruals": []}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)
    result = asyncio.run(
        client.record_paid_purchase(
            external_order_id="EP-NOPROMO",
            user_email="customer@example.com",
            promo=None,
            amount="5510.00",
            currency="RUB",
            paid_at="2026-07-26T12:00:00+00:00",
        )
    )
    assert result["accruals"] == []


def test_paid_purchase_reversal_uses_only_idempotent_order_identity(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "action": "reverse_paid_purchase",
            "external_order_id": "EP-REFUND1",
        }
        return httpx.Response(
            200,
            json={"ok": True, "data": {"outcome": "reversed"}},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        "src.integrations.bitrix_promo.httpx.AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    client = BitrixPromoClient(endpoint="https://example.test/api.php", token=TOKEN)

    result = asyncio.run(
        client.reverse_paid_purchase(external_order_id="EP-REFUND1")
    )

    assert result["outcome"] == "reversed"


def test_empty_configuration_is_rejected(monkeypatch):
    monkeypatch.setattr("src.integrations.bitrix_promo.BITRIX_PROMO_ENDPOINT", None)
    monkeypatch.setattr("src.integrations.bitrix_promo.BITRIX_PROMO_TOKEN", None)
    with pytest.raises(RuntimeError, match="not configured"):
        BitrixPromoClient()
