import logging

from typing import Any

import httpx
from fastapi import HTTPException

from config import YANDEX_DELIVERY_BASE_URL, YANDEX_DELIVERY_TOKEN
from src.database.models import Order
from src.integrations.delivery.cdek import get_cdek_client

from .fulfillment_payloads import build_cdek_order_body, build_yandex_delivery_request, normalize_address_for_cf

log = logging.getLogger(__name__)

YANDEX_HEADERS = {"Authorization": f"Bearer {YANDEX_DELIVERY_TOKEN}", "Accept": "application/json", "Content-Type": "application/json", "Accept-Language": "ru"}


def _offer_min_unix(offer: dict[str, Any]) -> int:
    try:
        return int((offer.get("offer_details") or {}).get("delivery_interval", {}).get("min"))
    except (TypeError, ValueError):
        return 10**18


async def _confirm_best_yandex_offer(client: httpx.AsyncClient, request_body: dict[str, Any]) -> dict[str, Any]:
    offers_response = await client.post(
        f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/offers/create",
        params={"send_unix": True},
        json=request_body,
        headers=YANDEX_HEADERS,
    )
    if offers_response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Yandex Delivery offers/create error: {offers_response.text}")

    offers = (offers_response.json()).get("offers") or []
    if not offers:
        raise HTTPException(status_code=502, detail="Yandex Delivery has no offers for this order")

    selected_offer = min(offers, key=_offer_min_unix)
    offer_id = selected_offer.get("offer_id")
    if not offer_id:
        raise HTTPException(status_code=502, detail="Yandex Delivery offer_id missing")

    confirm_response = await client.post(
        f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/offers/confirm",
        json={"offer_id": str(offer_id)},
        headers=YANDEX_HEADERS,
    )
    if confirm_response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Yandex Delivery offers/confirm error: {confirm_response.text}")
    return confirm_response.json()


async def _create_yandex_delivery(order: Order) -> dict[str, Any]:
    request_body = build_yandex_delivery_request(order)

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{YANDEX_DELIVERY_BASE_URL}/api/b2b/platform/request/create",
            params={"send_unix": True},
            json=request_body,
            headers=YANDEX_HEADERS,
        )
        if response.status_code == 404:
            data = await _confirm_best_yandex_offer(client, request_body)
        elif response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Yandex Delivery request/create error: {response.text}")
        else:
            data = response.json()

    request_id = data.get("request_id")
    return {
        "delivery_provider_ref": str(request_id or f"yandex:{order.order_number}"),
        "yandex_request_id": str(request_id) if request_id else None,
    }


def _extract_cdek_provider_ref(response: dict[str, Any], order: Order) -> str:
    entity = response.get("entity") or {}
    requests = response.get("requests") or []
    provider_ref = entity.get("uuid") or entity.get("cdek_number")
    if not provider_ref and requests and isinstance(requests[0], dict):
        provider_ref = requests[0].get("request_uuid")
    return str(provider_ref or f"cdek:{order.order_number}")


async def _create_cdek_delivery(order: Order) -> dict[str, Any]:
    cdek_client = get_cdek_client()
    order_body = await build_cdek_order_body(order, cdek_client)
    log.info("CDEK create_order request order_number=%s body=%s", order.order_number, order_body)
    response = await cdek_client.create_order(order_body)
    log.info("CDEK create_order response order_number=%s response=%s", order.order_number, response)
    return {"delivery_provider_ref": _extract_cdek_provider_ref(response, order)}


async def create_delivery_for_order(order: Order) -> dict[str, Any]:
    if order.delivery_created_at is not None:
        return {}

    service = (order.selected_delivery_service or "").strip().upper()
    if service == "YANDEX":
        return await _create_yandex_delivery(order)
    if service == "CDEK":
        return await _create_cdek_delivery(order)
    raise HTTPException(status_code=400, detail="Unsupported delivery service")
