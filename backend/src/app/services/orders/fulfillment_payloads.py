from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException

from config import CDEK_SENDER_NAME, CDEK_SENDER_PHONE, YANDEX_DELIVERY_WAREHOUSE_ID
from src.database.models import Order


def normalize_address_for_cf(address: object) -> str | None:
    if not address:
        return None
    if isinstance(address, str):
        value = address
    elif isinstance(address, dict):
        postal_code = address.get("postal_code")
        city = address.get("city")
        region = address.get("region")
        country_code = address.get("country_code")
        line = address.get("address") or address.get("formatted") or address.get("name")
        value = ", ".join(str(part) for part in [postal_code, city, region, country_code, line] if part)
    else:
        value = str(address)
    value = value.strip()
    return value[:255] if value else None


def _resolve_snapshot(order: Order) -> dict[str, Any]:
    snapshot = order.checkout_snapshot if isinstance(order.checkout_snapshot, dict) else {}
    selected_delivery = order.selected_delivery_payload if isinstance(order.selected_delivery_payload, dict) else {}
    if "selected_delivery" not in snapshot:
        snapshot = {**snapshot, "selected_delivery": selected_delivery}
    return snapshot


def _money_to_kopecks(value: Decimal) -> int:
    return int((Decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_yandex_delivery_request(order: Order) -> dict[str, Any]:
    snapshot = _resolve_snapshot(order)
    selected_delivery = snapshot.get("selected_delivery") or {}
    address = selected_delivery.get("address") or {}
    platform_station_id = address.get("code") or address.get("provider_reference")
    if not platform_station_id:
        raise HTTPException(status_code=400, detail="Yandex pickup platform station id is missing")

    total_kopecks = _money_to_kopecks(order.grand_total)
    return {
        "info": {
            "operator_request_id": str(order.order_number),
            "comment": snapshot.get("commentary") or order.comment or "Не указан",
        },
        "source": {"platform_station": {"platform_id": str(YANDEX_DELIVERY_WAREHOUSE_ID)}},
        "destination": {"type": "platform_station", "platform_station": {"platform_id": str(platform_station_id)}},
        "items": [
            {
                "count": 1,
                "name": f"Order #{order.order_number}",
                "article": f"ORDER-{order.order_number}",
                "billing_details": {
                    "unit_price": total_kopecks,
                    "assessed_unit_price": total_kopecks,
                    "nds": -1,
                },
                "physical_dims": {"dx": 25, "dy": 15, "dz": 10},
                "place_barcode": "box-1",
            }
        ],
        "places": [
            {
                "barcode": "box-1",
                "description": f"Box for order #{order.order_number}",
                "physical_dims": {
                    "dx": 25,
                    "dy": 15,
                    "dz": 10,
                    "weight_gross": 100,
                },
            }
        ],
        "billing_info": {"payment_method": "already_paid"},
        "recipient_info": {
            "first_name": order.recipient.name,
            "last_name": order.recipient.surname or "",
            "phone": order.recipient.phone,
            "email": order.recipient.email,
        },
        "last_mile_policy": "self_pickup",
        "particular_items_refuse": False,
        "forbid_unboxing": False,
    }


def _build_cdek_recipient(order: Order) -> dict[str, Any]:
    recipient_name = " ".join(part for part in [order.recipient.surname, order.recipient.name] if part).strip() or order.recipient.name
    recipient: dict[str, Any] = {"name": recipient_name, "phones": [{"number": order.recipient.phone}]}
    if order.recipient.email:
        recipient["email"] = order.recipient.email
    return recipient


def _build_cdek_order_items(order: Order) -> list[dict[str, Any]]:
    return [
        {
            "name": item.product_name,
            "ware_key": item.product_sku or str(item.product_id),
            "payment": {"value": 0},
            "cost": max(1, int(Decimal(item.unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))),
            "weight": 179,
            "amount": item.quantity,
            "comment": str(item.variant_id),
        }
        for item in order.items
    ]


async def build_cdek_order_body(order: Order, cdek_client: Any) -> dict[str, Any]:
    snapshot = _resolve_snapshot(order)
    selected_delivery = snapshot.get("selected_delivery") or {}
    address = selected_delivery.get("address") or {}
    delivery_mode = (selected_delivery.get("deliveryMode") or "").strip().lower()

    city_code = await cdek_client.get_city_code_by_coordinates(order.delivery_address.latitude, order.delivery_address.longitude)
    package = {"number": "1", "weight": 357, "length": 18, "width": 7, "height": 24, "items": _build_cdek_order_items(order)}
    order_body: dict[str, Any] = {
        "type": 1,
        "number": str(order.order_number),
        "tariff_code": cdek_client.tariff_codes["office" if delivery_mode == "office" else "door"],
        "comment": "Заказ из мобильного приложения",
        "recipient": _build_cdek_recipient(order),
        "sender": {"name": CDEK_SENDER_NAME, "phones": [{"number": CDEK_SENDER_PHONE}]},
        "from_location": cdek_client.from_location,
        "packages": [package],
        "delivery_recipient_cost": {"value": float(order.delivery_total)},
    }

    if delivery_mode == "office":
        provider_reference = address.get("code") or order.delivery_address.provider_reference
        if not provider_reference:
            raise HTTPException(status_code=400, detail="CDEK pickup point code is missing")
        order_body["delivery_point"] = str(provider_reference)
        return order_body

    city = address.get("city") or order.delivery_address.city
    postal_code = address.get("postal_code") or order.delivery_address.postal_code
    country_code = address.get("country_code") or order.delivery_address.country_code
    formatted = address.get("formatted") or address.get("address") or order.delivery_address.full_address
    if not city or not postal_code:
        raise HTTPException(status_code=400, detail="CDEK door delivery requires city and postal code")
    order_body["to_location"] = {
        "city": city,
        "postal_code": postal_code,
        "country_code": country_code,
        "address": formatted,
        "code": city_code,
    }
    return order_body
