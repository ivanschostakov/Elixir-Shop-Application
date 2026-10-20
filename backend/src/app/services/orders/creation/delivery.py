from typing import Any
from fastapi import HTTPException
from starlette import status
from src.database.models import OrderDraft
from src.integrations.delivery.cdek import get_cdek_client
from src.integrations.delivery.geo import get_geo_client
from src.integrations.delivery.schemas import COUNTRY_NAMES
from src.normalize import optional_str
from .common import log


def _country_name_from_code(country_code: Any) -> str | None:
    normalized_country_code = optional_str(country_code)
    if not normalized_country_code: return None
    return COUNTRY_NAMES.get(normalized_country_code.upper())  # type: ignore[arg-type]


def _geocode_query(address_payload: dict[str, Any]) -> str | None:
    latitude = address_payload.get("latitude")
    longitude = address_payload.get("longitude")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)): return f"{float(longitude):.6f},{float(latitude):.6f}"

    return (optional_str(address_payload.get("full_address")) or optional_str(address_payload.get("formatted")) or optional_str(address_payload.get("address")))


async def _enrich_selected_delivery_address_payload(address_payload: dict[str, Any]) -> None:
    country_name = (optional_str(address_payload.get("country")) or _country_name_from_code(address_payload.get("country_code")))
    if country_name: address_payload["country"] = country_name

    if all(optional_str(address_payload.get(field_name)) for field_name in ("city", "postal_code", "street", "house", "region")): return

    query = _geocode_query(address_payload)
    if not query: return

    try: geocode_result = await get_geo_client().geocode(address=query, lang="ru_RU", results=1)
    except Exception:
        log.warning("Failed to geocode delivery address payload query=%s", query, exc_info=True)
        return

    if optional_str(address_payload.get("city")) is None and geocode_result.city: address_payload["city"] = geocode_result.city
    if optional_str(address_payload.get("postal_code")) is None and geocode_result.postal_code: address_payload["postal_code"] = geocode_result.postal_code
    if optional_str(address_payload.get("country_code")) is None and geocode_result.country_code: address_payload["country_code"] = geocode_result.country_code
    if optional_str(address_payload.get("country")) is None and geocode_result.country: address_payload["country"] = geocode_result.country
    if optional_str(address_payload.get("region")) is None and geocode_result.region: address_payload["region"] = geocode_result.region
    if optional_str(address_payload.get("street")) is None and geocode_result.street: address_payload["street"] = geocode_result.street
    if optional_str(address_payload.get("house")) is None and geocode_result.house: address_payload["house"] = geocode_result.house


async def _build_selected_delivery_payload(draft: OrderDraft) -> tuple[str, dict[str, Any]]:
    if draft.delivery_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery address is required")

    delivery_address = draft.delivery_address
    address_payload = {
        "code": delivery_address.provider_reference,
        "name": delivery_address.name,
        "address": delivery_address.full_address,
        "formatted": delivery_address.full_address,
        "full_address": delivery_address.full_address,
        "details": delivery_address.details,
        "city": delivery_address.city,
        "postal_code": delivery_address.postal_code,
        "country_code": delivery_address.country_code,
        "latitude": delivery_address.latitude,
        "longitude": delivery_address.longitude,
        "provider_reference": delivery_address.provider_reference,
    }
    await _enrich_selected_delivery_address_payload(address_payload)
    delivery_total = float(draft.delivery_total)

    if delivery_address.provider == "CDEK":
        delivery_mode = "office" if delivery_address.mode == "pickup" else "door"
        payload = {
            "deliveryMode": delivery_mode,
            "tariff": {
                "tariff_code": get_cdek_client().tariff_codes[delivery_mode],
                "tariff_name": delivery_mode,
                "delivery_sum": delivery_total,
            },
            "address": address_payload,
            "delivery_sum": delivery_total,
        }
        return "CDEK", payload

    if delivery_address.provider == "YANDEX":
        if delivery_address.mode != "pickup": raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Yandex door delivery is not supported in this flow")
        payload = {
            "deliveryMode": "self_pickup",
            "tariff": {"tariff_name": "self_pickup"},
            "address": address_payload,
            "delivery_sum": delivery_total,
        }
        return "YANDEX", payload

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported delivery provider")
