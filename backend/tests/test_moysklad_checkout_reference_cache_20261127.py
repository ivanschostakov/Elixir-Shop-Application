import asyncio
from collections import Counter
from uuid import UUID, uuid4

import httpx
import pytest

from src.integrations.moysklad.client import MoySkladClient, reference_cache
from src.integrations.moysklad.client.common import CUSTOMER_ORDER_ATTR_IDS
from src.integrations.moysklad.order_sync import organization
from src.integrations.moysklad.settlement_checkout import verify_ruble_currency

pytestmark = pytest.mark.anyio
SERVICE = "/entity/service"
DELIVERY = {"filter": "name=Доставка заказа;archived=false"}
ATTRIBUTES = "/entity/customerorder/metadata/attributes"


@pytest.fixture
async def make_client():
    clients = []

    def make(reply, *, token="test-a"):
        calls = Counter()
        async def handle(request):
            path = request.url.path
            calls[path] += 1
            await asyncio.sleep(0)
            return reply(path, request.url.params, calls[path])

        client = MoySkladClient(base_url="https://cache.test", token=token)
        client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handle))
        clients.append(client)
        return client, calls

    yield make
    for client in clients:
        await client.aclose()


def ok(data):
    return httpx.Response(200, json=data)


async def test_checkout_uses_one_request_per_reference(make_client, monkeypatch):
    org_id, service_id, currency_id = (str(uuid4()) for _ in range(3))
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_ID", org_id)
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_NAME", "Seller")
    dictionary = {key: f"/entity/customentity/{uuid4()}" for key in ("payment_method", "delivery_method")}
    payloads = {
        f"/entity/organization/{org_id}": {"id": org_id, "name": "Seller"},
        "/entity/organization": {"rows": [{"id": org_id, "name": "Seller"}]},
        "/entity/store": {"rows": [{"name": "Store"}]},
        SERVICE: {"rows": [{"id": service_id, "name": "Доставка заказа"}]},
        "/entity/country": {"rows": [{"name": "Russia", "code": "RU"}]},
        "/entity/region": {"rows": [{"name": "г Москва"}]},
        "/entity/customerorder/metadata": {"states": [{"name": "New"}]},
        "/entity/invoiceout/metadata": {"states": [{"name": "Paid"}]},
        ATTRIBUTES: {"rows": [{"id": CUSTOMER_ORDER_ATTR_IDS[k], "customEntityMeta": {"href": v + "/metadata"}}
                              for k, v in dictionary.items()]},
        **{path: {"rows": [{"name": key}]} for key, path in dictionary.items()},
        f"/entity/currency/{currency_id}": {"id": currency_id, "isoCode": "RUB", "code": 643, "rate": 1},
    }
    client, calls = make_client(lambda path, params, n: ok(payloads[path]))
    for _ in range(2):
        assert await organization._resolve_organization_id(client) == UUID(org_id)
        assert (await client.find_organization_by_name("Seller"))["id"] == org_id
        assert await client.find_store_by_name("Store")
        assert (await client.get_all(SERVICE, **DELIVERY))[0]["id"] == service_id
        assert await client.find_country_by_name_or_code("RU")
        assert await client.find_region_by_name("Москва")
        assert await client.find_customerorder_state_by_name("New")
        assert await client.find_invoiceout_state_by_name("Paid")
        for key in dictionary:
            assert await client.find_customerorder_customentity_value(key, key)
        assert await client.get_currency_identity(currency_id) == {"id": currency_id, "isoCode": "RUB", "code": 643}
    assert calls == {path: 1 for path in payloads}


async def test_concurrent_reads_return_independent_values_and_do_not_cross_accounts(make_client):
    def reply(owner):
        return lambda path, params, n: ok({"rows": [{"meta": {"owner": owner}}]})

    a, a_calls = make_client(reply("A"))
    b, b_calls = make_client(reply("B"), token="test-b")
    rows = await asyncio.gather(*(a.get_stores() for _ in range(12)))
    rows[0][0]["meta"]["owner"] = "changed"
    assert all(result[0]["meta"]["owner"] == "A" for result in rows[1:])
    assert (await a.get_stores())[0]["meta"]["owner"] == "A"
    assert (await b.get_stores())[0]["meta"]["owner"] == "B"
    assert a_calls == b_calls == {"/entity/store": 1}


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_expired_reference_does_not_mask_failure_and_next_call_retries(make_client, monkeypatch, status):
    now = [0]
    monkeypatch.setattr(reference_cache, "monotonic", lambda: now[0])
    client, calls = make_client(lambda path, params, n: httpx.Response(status) if n == 2 else ok({"rows": [{"n": n}]}))
    assert (await client.get_stores())[0]["n"] == 1
    now[0] = 3599
    assert (await client.get_stores())[0]["n"] == 1
    now[0] += 1
    with pytest.raises(httpx.HTTPStatusError) as error:
        await client.get_stores()
    assert error.value.response.status_code == status
    assert (await client.get_stores())[0]["n"] == 3
    assert calls == {"/entity/store": 3}


@pytest.mark.parametrize("second", [httpx.Response(503), ok({"errors": [{}]}), ok({"rows": [None]}), ok({"rows": []})])
async def test_partial_dictionary_is_never_returned_or_cached(make_client, second):
    def reply(path, params, n):
        if params["offset"] == "0":
            return ok({"meta": {"size": 2}, "rows": [{"name": "first"}]})
        assert params["offset"] == "1"
        return second if n == 2 else ok({"rows": [{"name": "last"}]})

    client, calls = make_client(reply)
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        await client.get_countries()
    for _ in range(2):
        assert await client.get_countries() == [{"name": "first"}, {"name": "last"}]
    assert calls == {"/entity/country": 4}


async def test_empty_and_ambiguous_delivery_do_not_hide_repair(make_client):
    row = {"id": str(uuid4()), "name": "Доставка заказа"}
    replies = [[], [row, dict(row, id=str(uuid4()))], [row]]
    client, calls = make_client(lambda path, params, n: ok({"rows": replies[n - 1]}))
    for count in (0, 2, 1, 1):
        assert len(await client.get_all(SERVICE, **DELIVERY)) == count
    assert calls == {SERVICE: 3}


@pytest.mark.parametrize(("path", "params"), [
    (SERVICE, {}), (SERVICE, {"filter": "archived=false"}), (SERVICE, {**DELIVERY, "expand": "owner"}),
    ("/entity/store", {"search": "north"}), ("/entity/customentity/" + str(uuid4()), {}),
    ("/entity/customerorder", {}), ("/entity/invoiceout", {}), ("/entity/paymentin", {}),
    ("/entity/counterparty", {}), ("/report/stock/all", {}),
])
async def test_other_get_all_requests_always_read_live(make_client, path, params):
    client, calls = make_client(lambda path, params, n: ok({"rows": [{"version": n}]}))
    for n in (1, 2):
        assert await client.get_all(path, **params) == [{"version": n}]
    assert calls == {path: 2}


async def test_live_order_and_external_code_lookup_are_not_cached(make_client):
    order_id = str(uuid4())
    path = "/entity/customerorder"
    def reply(url, params, n):
        row = {"id": order_id, "externalCode": "checkout", "version": n}
        if url == path:
            assert params["filter"] == "externalCode=checkout"
            return ok({"rows": [row]})
        return ok(row)

    client, calls = make_client(reply)
    for n in (1, 2):
        assert (await client.get_customer_order(order_id))["version"] == n
        assert (await client._find_entity_by_external_code("customerorder", "checkout"))["version"] == n
    assert calls == {path: 2, path + "/" + order_id: 2}


async def test_currency_wrong_identity_and_org_not_found_retry(make_client):
    entity_id = str(uuid4())
    def reply(path, params, n):
        if "organization" in path:
            return httpx.Response(404) if n == 1 else ok({"id": entity_id, "name": "Seller"})
        return ok({"id": str(uuid4()) if n == 1 else entity_id, "isoCode": "RUB", "code": "643"})

    client, calls = make_client(reply)
    assert await client.get_organization(entity_id) is None
    with pytest.raises(ValueError, match="identity"):
        await client.get_currency_identity(entity_id)
    for _ in range(2):
        assert (await client.get_currency_identity(entity_id))["id"] == entity_id
        assert (await client.get_organization(entity_id))["id"] == entity_id
    assert calls == {f"/entity/{kind}/{entity_id}": 2 for kind in ("currency", "organization")}


async def test_settlement_cannot_use_previous_ruble_identity_after_one_hour(make_client, monkeypatch):
    uid = uuid4()
    order = {"rate": {"currency": {"id": str(uid)}}}
    now = 0
    monkeypatch.setattr(reference_cache, "monotonic", lambda: now)
    replies = [ok({"id": str(uid), "isoCode": "RUB", "code": 643}), httpx.Response(503),
               ok({"id": str(uid), "isoCode": "USD", "code": "840"})]
    client, calls = make_client(lambda path, params, n: replies[n - 1])
    assert await verify_ruble_currency(client, order) == uid
    now = 3599
    assert await verify_ruble_currency(client, order) == uid
    now = 3600
    with pytest.raises(httpx.HTTPStatusError):
        await verify_ruble_currency(client, order)
    with pytest.raises(ValueError, match="Only RUB"):
        await verify_ruble_currency(client, order)
    assert calls == {f"/entity/currency/{uid}": 3}


async def test_method_values_use_verified_binding_and_attribute_page_limit(make_client):
    paths = {key: f"/entity/customentity/{uuid4()}" for key in ("payment_method", "delivery_method")}
    bindings = [{"id": CUSTOMER_ORDER_ATTR_IDS[key], "customEntityMeta": {"href": path}} for key, path in paths.items()]
    def reply(path, params, n):
        if path == ATTRIBUTES:
            if n == 1:
                return ok({"rows": [bindings[0], bindings[0]]})
            if n == 2:
                return ok({"rows": [dict(bindings[0], customEntityMeta={})]})
            return ok({"rows": bindings if params["limit"] == "1000" else bindings[1:]})
        assert path == paths["payment_method"]
        return ok({"rows": [{"name": "Card"}]})

    client, calls = make_client(reply)
    with pytest.raises(ValueError, match="Ambiguous"):
        await client.get_customerorder_customentity_values("payment_method")
    assert await client.get_customerorder_customentity_values("payment_method") == []
    for _ in range(2):
        assert await client.find_customerorder_customentity_value("payment_method", "Card")
    assert await client.get_customerorder_customentity_values("payment_method", limit=1) == []
    assert calls == {ATTRIBUTES: 4, paths["payment_method"]: 1}


async def test_archived_or_ambiguous_organization_is_not_selected(make_client, monkeypatch):
    org_id = str(uuid4())
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_ID", org_id)
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_NAME", "Seller")
    row = {"id": org_id, "name": "Seller", "archived": True}
    active = [dict(row, archived=False, id=str(uuid4())) for _ in range(2)]
    client, calls = make_client(lambda path, params, n: ok(row if path.endswith(org_id) else {"rows": [row, *active]}))
    with pytest.raises(ValueError, match="Ambiguous"):
        await organization._resolve_organization_id(client)
    assert calls == {"/entity/organization": 1, "/entity/organization/" + org_id: 1}


async def test_cached_list_cannot_reinstate_rejected_organization_id(make_client, monkeypatch):
    org_id = str(uuid4())
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_ID", org_id)
    monkeypatch.setattr(organization, "MOY_SKLAD_ORGANIZATION_NAME", "Seller")
    path = "/entity/organization"
    client, calls = make_client(lambda url, params, n: ok({"rows": [{"id": org_id, "name": "Seller"}]})
                                if url == path else httpx.Response(404))
    assert await client.find_organization_by_name("Seller")
    assert await organization._resolve_organization_id(client) is None
    assert calls == {path: 1, path + "/" + org_id: 1}


async def test_bad_states_are_not_cached(make_client):
    replies = [{"errors": [{"message": "bad"}]}, {"states": [None]}, {"states": []}, {"states": [{"name": "New"}]}]
    client, calls = make_client(lambda path, params, n: ok(replies[n - 1]))
    for _ in range(2):
        with pytest.raises(ValueError):
            await client.get_customerorder_states()
    assert await client.get_customerorder_states() == []
    for _ in range(2):
        assert await client.find_customerorder_state_by_name("New")
    assert calls == {"/entity/customerorder/metadata": 4}
