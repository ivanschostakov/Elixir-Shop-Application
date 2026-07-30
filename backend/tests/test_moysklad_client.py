import pytest

from src.integrations.moysklad.client import MoySkladClient


@pytest.mark.anyio
async def test_get_counterparty_by_phone_normalizes_search_and_matches_counterparty_phone(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")
    recorded_call: dict[str, object] = {}

    async def fake_get_page(path: str, *, limit: int = 100, offset: int = 0, **params):
        recorded_call.update({
            "path": path,
            "limit": limit,
            "offset": offset,
            "params": params,
        })
        return {
            "rows": [
                {"id": "counterparty-1", "phone": "+7 999 000-00-00"},
                {"id": "counterparty-2", "phone": "+7 999 000-00-01"},
            ]
        }

    monkeypatch.setattr(client, "get_page", fake_get_page)

    result = await client.get_counterparty_by_phone(" +7 (999) 000-00-00 ")

    assert result == {"id": "counterparty-1", "phone": "+7 999 000-00-00"}
    assert recorded_call == {
        "path": "/entity/counterparty",
        "limit": 100,
        "offset": 0,
        "params": {
            "search": "+79990000000",
            "expand": "contactpersons",
        },
    }


@pytest.mark.anyio
async def test_get_counterparty_by_phone_matches_contactperson_phone(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")

    async def fake_get_page(_path: str, *, limit: int = 100, offset: int = 0, **params):
        assert limit == 100
        assert offset == 0
        assert params["search"] == "+79990000000"
        return {
            "rows": [
                {"id": "counterparty-1", "phone": "+7 999 000-00-01"},
                {
                    "id": "counterparty-2",
                    "contactpersons": {
                        "rows": [
                            {"phone": "+7 (999) 000-00-00"},
                        ]
                    },
                },
            ]
        }

    monkeypatch.setattr(client, "get_page", fake_get_page)

    result = await client.get_counterparty_by_phone("+7 999 000-00-00")

    assert result == {
        "id": "counterparty-2",
        "contactpersons": {
            "rows": [
                {"phone": "+7 (999) 000-00-00"},
            ]
        },
    }


@pytest.mark.anyio
async def test_get_counterparty_by_phone_returns_none_for_blank_phone(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")

    async def fail_get_page(*_args, **_kwargs):
        raise AssertionError("get_page should not be called for blank phone")

    monkeypatch.setattr(client, "get_page", fail_get_page)

    result = await client.get_counterparty_by_phone("  ")

    assert result is None


@pytest.mark.anyio
async def test_get_counterparty_by_email_normalizes_and_matches_exact_email(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")
    recorded_call: dict[str, object] = {}

    async def fake_get_page(path: str, *, limit: int = 100, offset: int = 0, **params):
        recorded_call.update({"path": path, "limit": limit, "offset": offset, "params": params})
        return {
            "rows": [
                {"id": "counterparty-1", "email": "other@example.com"},
                {"id": "counterparty-2", "email": "Customer@Example.com"},
            ]
        }

    monkeypatch.setattr(client, "get_page", fake_get_page)

    result = await client.get_counterparty_by_email(" Customer@Example.com ")

    assert result == {"id": "counterparty-2", "email": "Customer@Example.com"}
    assert recorded_call == {
        "path": "/entity/counterparty",
        "limit": 100,
        "offset": 0,
        "params": {
            "search": "customer@example.com",
            "expand": "contactpersons",
        },
    }


@pytest.mark.anyio
async def test_get_counterparty_by_email_matches_contactperson_email(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")

    async def fake_get_page(*_args, **_kwargs):
        return {
            "rows": [
                {
                    "id": "counterparty-1",
                    "contactpersons": {"rows": [{"email": "customer@example.com"}]},
                }
            ]
        }

    monkeypatch.setattr(client, "get_page", fake_get_page)

    result = await client.get_counterparty_by_email("customer@example.com")

    assert result == {
        "id": "counterparty-1",
        "contactpersons": {"rows": [{"email": "customer@example.com"}]},
    }


@pytest.mark.anyio
async def test_get_counterparty_by_email_does_not_accept_inexact_search_result(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")

    async def fake_get_page(*_args, **_kwargs):
        return {"rows": [{"id": "counterparty-1", "email": "other@example.com"}]}

    monkeypatch.setattr(client, "get_page", fake_get_page)

    assert await client.get_counterparty_by_email("customer@example.com") is None


@pytest.mark.anyio
async def test_fetch_catalog_rows_excludes_raw_material_folder_but_keeps_cosmetic_products(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")
    cosmetic_product_id = "7c582468-13e1-11f1-0a80-176100294be8"
    raw_product_id = "bde05938-52bf-11f1-0a80-032c003c7a1b"

    async def fake_get_all(path: str, **_params):
        if path == "/entity/product":
            return [
                {
                    "id": cosmetic_product_id,
                    "externalCode": "cosmetic-capixyl",
                    "article": "00-00000123",
                    "name": "Capixyl 50% (Косметическое сырье)",
                    "pathName": "Косметические пептиды (кожа, волосы, загар)",
                },
                {
                    "id": raw_product_id,
                    "externalCode": "raw-capixyl",
                    "code": "НФ-00000515",
                    "name": "Сырье Capixyl 50%",
                    "pathName": "Сырье и материалы",
                },
            ]
        return []

    monkeypatch.setattr(client, "get_all", fake_get_all)

    products, variants, stats = await client.fetch_catalog_rows()

    assert [row.name for row in products] == ["Capixyl 50% (Косметическое сырье)"]
    assert len(variants) == 1
    assert str(variants[0].product_system_id) == cosmetic_product_id
    assert stats.fetched_products == 1


@pytest.mark.anyio
async def test_resolve_or_create_bonus_transaction_builds_spending_payload(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")
    counterparty_id = "12345678-1234-1234-1234-123456789012"
    program_id = "87654321-4321-4321-4321-210987654321"
    recorded: dict[str, object] = {}

    async def fake_find(_external_code: str):
        return None

    async def fake_create(entity_type: str, payload: dict):
        recorded["entity_type"] = entity_type
        recorded["payload"] = payload
        return {"id": "transaction-1", **payload}

    monkeypatch.setattr(client, "find_bonus_transaction_by_external_code", fake_find)
    monkeypatch.setattr(client, "_create_entity", fake_create)

    result = await client.resolve_or_create_bonus_transaction(
        counterparty_id=counterparty_id,
        bonus_program_id=program_id,
        bonus_points=70,
        transaction_type="SPENDING",
        external_code="elixir-bonus-spend-EP-TEST",
        name="Списание бонусов",
        description="Заказ EP-TEST",
    )

    assert result["id"] == "transaction-1"
    assert recorded["entity_type"] == "bonustransaction"
    payload = recorded["payload"]
    assert isinstance(payload, dict)
    assert payload["bonusValue"] == 70
    assert payload["transactionType"] == "SPENDING"
    assert payload["externalCode"] == "elixir-bonus-spend-EP-TEST"
    assert payload["agent"]["meta"]["href"].endswith(f"/entity/counterparty/{counterparty_id}")
    assert payload["bonusProgram"]["meta"]["href"].endswith(f"/entity/bonusprogram/{program_id}")


@pytest.mark.anyio
async def test_resolve_or_create_bonus_transaction_reuses_existing_transaction(monkeypatch):
    client = MoySkladClient(token="token", base_url="https://example.test/api/remap/1.2")
    existing = {"id": "transaction-1", "externalCode": "same-order"}

    async def fake_find(_external_code: str):
        return existing

    async def fail_create(*_args, **_kwargs):
        raise AssertionError("existing transaction must be reused")

    monkeypatch.setattr(client, "find_bonus_transaction_by_external_code", fake_find)
    monkeypatch.setattr(client, "_create_entity", fail_create)

    result = await client.resolve_or_create_bonus_transaction(
        counterparty_id="12345678-1234-1234-1234-123456789012",
        bonus_program_id="87654321-4321-4321-4321-210987654321",
        bonus_points=70,
        transaction_type="SPENDING",
        external_code="same-order",
        name="Списание бонусов",
    )

    assert result is existing
