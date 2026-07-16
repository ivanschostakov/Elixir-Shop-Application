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
