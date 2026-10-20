from decimal import Decimal
import re
from typing import Any
from src.database.models import Order
from src.integrations.delivery.schemas import COUNTRY_NAMES
from src.normalize import coerce_uuid, extract_dict, optional_str
from src.integrations.moysklad.client import MoySkladClient
from .common import _APARTMENT_RE, _BUILDING_HINT_RE, _HOUSE_RE, _REGION_HINT_RE, _STREET_HINT_RE


def _delivery_cost_value(order: Order) -> str:
    return f"{Decimal(order.delivery_total):.2f}"


def _decimal_or_zero(value: Any) -> Decimal:
    try: return Decimal(str(value))
    except Exception: return Decimal("0.00")


def _shipment_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        full = optional_str(order.delivery_address.full_address)
        if full: return full
    return optional_str(order.delivery_string)


def _address_segments(full: str) -> list[str]:
    return [segment.strip() for segment in full.split(",") if optional_str(segment)]


def _extract_street(full: str) -> str | None:
    for segment in _address_segments(full):
        if _STREET_HINT_RE.search(segment): return segment
    return None


def _extract_house(full: str, *, street: str | None = None) -> str | None:
    explicit = _HOUSE_RE.search(full)
    if explicit: return optional_str(explicit.group(1))

    segments = _address_segments(full)
    if not segments: return None
    if street is None: street = _extract_street(full)
    if not street: return None

    for index, segment in enumerate(segments):
        if segment != street: continue
        if index + 1 >= len(segments): return None
        next_segment = segments[index + 1]
        if not re.fullmatch(r"[0-9A-Za-zА-Яа-я/-]+", next_segment): return None
        if index + 2 < len(segments) and _BUILDING_HINT_RE.search(segments[index + 2]): return f"{next_segment}, {segments[index + 2]}"
        return next_segment
    return None


def _extract_apartment(full: str) -> str | None:
    apartment = _APARTMENT_RE.search(full)
    if apartment: return optional_str(apartment.group(1))
    return None


def _extract_region(full: str) -> str | None:
    for segment in _address_segments(full):
        if _REGION_HINT_RE.search(segment): return segment
    return None


def _country_name_from_payload(country_name: Any, country_code: Any) -> str | None:
    normalized_name = optional_str(country_name)
    if normalized_name: return normalized_name
    normalized_code = optional_str(country_code)
    if not normalized_code: return None
    return COUNTRY_NAMES.get(normalized_code.upper())  # type: ignore[arg-type]


async def _shipment_address_full(order: Order, *, moysklad_client: MoySkladClient) -> dict[str, Any] | None:
    payload = extract_dict(order.selected_delivery_payload)
    address = extract_dict(payload.get("address"))
    full = optional_str(address.get("full_address")) or optional_str(address.get("formatted")) or optional_str(address.get("address")) or _shipment_address(order)
    if not full: return None

    result: dict[str, Any] = {}
    city = optional_str(address.get("city")) or (optional_str(order.delivery_address.city) if order.delivery_address is not None else None)
    postal = optional_str(address.get("postal_code")) or (optional_str(order.delivery_address.postal_code) if order.delivery_address is not None else None)
    details = optional_str(address.get("details")) or (optional_str(order.delivery_address.details) if order.delivery_address is not None else None)
    street = optional_str(address.get("street")) or _extract_street(full)
    house = optional_str(address.get("house")) or _extract_house(full, street=street)
    apartment = optional_str(address.get("apartment")) or _extract_apartment(full)
    region_name = optional_str(address.get("region")) or _extract_region(full)
    country_code = optional_str(address.get("country_code")) or (optional_str(order.delivery_address.country_code) if order.delivery_address is not None else None)
    country_name = _country_name_from_payload(address.get("country"), country_code)
    country_row = await moysklad_client.find_country_by_name_or_code(country_code or "", country_name or "")

    if city: result["city"] = city
    if postal: result["postalCode"] = postal
    if details: result["comment"] = details
    if street: result["street"] = street
    if house: result["house"] = house
    if apartment: result["apartment"] = apartment
    if country_row and isinstance(country_row.get("meta"), dict): result["country"] = {"meta": country_row["meta"]}
    if region_name:
        country_id = coerce_uuid(country_row.get("id")) if country_row is not None else None
        region_row = await moysklad_client.find_region_by_name(region_name, country_id=country_id)
        if region_row and isinstance(region_row.get("meta"), dict): result["region"] = {"meta": region_row["meta"]}
    # MoySklad renders shipmentAddressFull as a combined human string.
    # Sending the full address in addInfo alongside structured fields duplicates the address in UI.
    has_structured_location = any(result.get(field_name) for field_name in ("city", "postalCode", "street", "house", "apartment"))
    if not has_structured_location: result["addInfo"] = full
    return result
