from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from src.app.services import delivery_quotes
from src.integrations.bitrix_delivery import BitrixDeliveryError


def _request_quote(cdek):
    return delivery_quotes.calculate_authoritative_cdek_quote(
        None, user=SimpleNamespace(email=None), items=[], cdek=cdek,
        address=dict(provider="CDEK", mode="pickup", provider_reference="TEST", country_code="RU",
                     latitude=55, longitude=37),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "http_503"])
async def test_fias_lookup_outage_is_retryable_without_requoting(monkeypatch, failure):
    bitrix_quote = AsyncMock(side_effect=BitrixDeliveryError(
        status_code=422, code="destination_not_found", message_ru="missing", message_en="missing",
    ))
    monkeypatch.setattr(delivery_quotes, "BitrixDeliveryClient", lambda: SimpleNamespace(quote=bitrix_quote))
    monkeypatch.setattr(delivery_quotes, "build_bitrix_delivery_items", AsyncMock(return_value=[]))
    cdek = delivery_quotes.get_cdek_client()
    request = AsyncMock(
        return_value=httpx.Response(503 if failure == "http_503" else 200, text="upstream detail"),
        side_effect=httpx.ReadTimeout("timeout") if failure == "timeout" else None,
    )
    monkeypatch.setattr(cdek, "get_delivery_point_city_code", AsyncMock(return_value=17))
    monkeypatch.setattr(cdek, "_ensure_token", AsyncMock(return_value="test"))
    monkeypatch.setattr(cdek._httpx_client, "request", request)
    with pytest.raises(HTTPException) as caught:
        await _request_quote(cdek)
    assert caught.value.status_code == 502
    assert "позже" in caught.value.detail
    assert "upstream detail" not in caught.value.detail
    request.assert_awaited_once()
    assert request.await_args.kwargs["url"] == "/v2/location/cities"
    assert request.await_args.kwargs["params"] == {"code": 17, "country_codes": "RU"}
    bitrix_quote.assert_awaited_once()


@pytest.mark.anyio
async def test_direct_bitrix_quote_skips_fias(monkeypatch):
    quoted = {"delivery_sum": 345, "currency": "RUB"}
    bitrix_quote = AsyncMock(return_value=quoted)
    monkeypatch.setattr(delivery_quotes, "BitrixDeliveryClient", lambda: SimpleNamespace(quote=bitrix_quote))
    monkeypatch.setattr(delivery_quotes, "build_bitrix_delivery_items", AsyncMock(return_value=[]))
    cdek = SimpleNamespace(get_delivery_point_city_code=AsyncMock(return_value=17), city_fias_guid=AsyncMock())
    result = await _request_quote(cdek)
    assert result is quoted
    bitrix_quote.assert_awaited_once()
    cdek.city_fias_guid.assert_not_awaited()
