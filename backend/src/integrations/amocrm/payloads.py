from decimal import Decimal

from .schemas.common import AmoCustomFieldByCode, AmoCustomFieldById, AmoValue
from .schemas.contact import ContactCreatePayload, ContactUpdatePayload
from .schemas.lead import (
    LeadCreatePayload, LeadLinkPayload, LeadNoteCreatePayload, LeadNoteParams,
)
from .utils import normalize_phone


def build_contact_custom_fields(phone: str | None, email: str | None) -> list[AmoCustomFieldByCode]:
    fields: list[AmoCustomFieldByCode] = []
    normalized_phone = normalize_phone(phone)
    normalized_email = email.strip().lower() if email else None
    if normalized_phone: fields.append(AmoCustomFieldByCode(field_code="PHONE", values=[AmoValue(value=normalized_phone, enum_code="WORK")]))
    if normalized_email:fields.append(AmoCustomFieldByCode(field_code="EMAIL", values=[AmoValue(value=normalized_email, enum_code="WORK")]))

    return fields


def build_contact_create_payload(*, name: str, phone: str | None, email: str | None) -> ContactCreatePayload: return ContactCreatePayload(name=name, custom_fields_values=build_contact_custom_fields(phone, email))
def build_contact_update_payload(*, contact_id: int, name: str | None = None, phone: str | None = None, email: str | None = None) -> ContactUpdatePayload:
    custom_fields = build_contact_custom_fields(phone, email)
    return ContactUpdatePayload(id=contact_id, name=name, custom_fields_values=custom_fields or None)


def build_lead_custom_fields(custom_fields: dict[int, object] | None) -> list[AmoCustomFieldById]:
    if not custom_fields: return []
    result: list[AmoCustomFieldById] = []
    for field_id, value in custom_fields.items():
        if value is None:continue
        result.append(AmoCustomFieldById(field_id=field_id, values=[AmoValue(value=str(value))]))
        
    return result


def build_lead_create_payload(*, name: str, pipeline_id: int, status_id: int, price: int | None = None, custom_fields: dict[int, object] | None = None) -> LeadCreatePayload: return LeadCreatePayload(name=name, pipeline_id=pipeline_id, status_id=status_id, price=price, custom_fields_values=build_lead_custom_fields(custom_fields))
def build_lead_note_payload(*, lead_id: int, text: str) -> LeadNoteCreatePayload: return LeadNoteCreatePayload(entity_id=lead_id, params=LeadNoteParams(text=text))
def build_lead_link_payload(*, contact_id: int) -> LeadLinkPayload: return LeadLinkPayload(to_entity_id=contact_id)


def build_order_lead_custom_fields(*, cf: dict[str, int], address_str: str, order_number: str, delivery_service: str, payment_method: str, tg_nick: str | None = None, delivery_sum: Decimal | float | int | None = None) -> dict[int, object]:
    result: dict[int, object] = {}

    if address_str: result[cf["address"]] = address_str
    if tg_nick: result[cf["tg_nick"]] = tg_nick
    if delivery_sum is not None: result[cf["delivery_sum"]] = float(delivery_sum)

    delivery_service_normalized = (delivery_service or "").strip().upper()
    if delivery_service_normalized == "CDEK":
        result[cf["delivery_cdek"]] = "СДЭК"
        result[cf["cdek_number"]] = order_number
        result[cf["cdek_tracking_url"]] = f"https://www.cdek.ru/ru/tracking/?order_id={order_number}"

    elif delivery_service_normalized == "YANDEX": result[cf["delivery_yandex"]] = "Яндекс"
    result[cf["payment"]] = payment_method
    return result