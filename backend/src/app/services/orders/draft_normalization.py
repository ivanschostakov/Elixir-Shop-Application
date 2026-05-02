from fastapi import HTTPException
from starlette import status

from src.database.limits import EMAIL_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, WEBSITE_PHONE_MAX_LENGTH
from src.database.models import OrderDraft
from src.database.schemas import DeliveryAddressCreate, DeliveryRecipientCreate
from src.normalize import fit_text, normalize_person_name, optional_str

CREATE_ORDER_DRAFT_DELIVERY_FIELDS = ("mode", "provider", "country_code", "name", "full_address", "details", "city", "postal_code", "latitude", "longitude", "provider_reference", "delivery_calculation")
REQUIRED_CREATE_ORDER_DRAFT_DELIVERY_FIELDS = ("mode", "provider", "country_code", "name", "full_address", "latitude", "longitude", "delivery_calculation")


def _normalize_required_recipient_text(value: str | None, *, max_length: int, field_name: str) -> str:
    normalized = normalize_person_name(value, max_length=max_length)
    if normalized is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return normalized


def _normalize_recipient_contact(value: str | None, *, max_length: int) -> str: return fit_text(optional_str(value), max_length) or ""
def _normalize_order_draft_text(value: str | None, *, max_length: int) -> str | None: return fit_text(optional_str(value), max_length)


def _require_delivery_value(value, *, field_name: str):
    if value is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return value


def _build_new_recipient_data(user_id: int, payload) -> DeliveryRecipientCreate:
    return DeliveryRecipientCreate(
        user_id=user_id,
        name=_normalize_required_recipient_text(payload.name, max_length=PERSON_NAME_MAX_LENGTH, field_name="Recipient name"),
        surname=_normalize_required_recipient_text(payload.surname, max_length=PERSON_NAME_MAX_LENGTH, field_name="Recipient surname"),
        phone=_normalize_recipient_contact(payload.phone, max_length=WEBSITE_PHONE_MAX_LENGTH),
        email=_normalize_recipient_contact(payload.email, max_length=EMAIL_MAX_LENGTH),
    )


def _build_create_delivery_address_data(user_id: int, payload) -> DeliveryAddressCreate:
    full_address = optional_str(payload.full_address)
    if full_address is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Address is required")

    return DeliveryAddressCreate(
        user_id=user_id,
        mode=_require_delivery_value(payload.mode, field_name="Delivery mode"),
        provider=_require_delivery_value(payload.provider, field_name="Delivery provider"),
        country_code=_require_delivery_value(payload.country_code, field_name="Delivery country"),
        name=optional_str(payload.name) or full_address,
        full_address=full_address,
        details=optional_str(payload.details),
        city=optional_str(payload.city),
        postal_code=optional_str(payload.postal_code),
        latitude=_require_delivery_value(payload.latitude, field_name="Delivery latitude"),
        longitude=_require_delivery_value(payload.longitude, field_name="Delivery longitude"),
        provider_reference=optional_str(payload.provider_reference),
    )


def _build_new_delivery_address_data(draft: OrderDraft, payload) -> DeliveryAddressCreate:
    full_address = optional_str(payload.full_address)
    if full_address is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Address is required")

    template = draft.delivery_address
    fields = payload.model_fields_set
    mode = payload.mode if payload.mode is not None else template.mode if template is not None else None
    provider = payload.provider if payload.provider is not None else template.provider if template is not None else None
    country_code = payload.country_code if payload.country_code is not None else template.country_code if template is not None else None
    latitude = payload.latitude if payload.latitude is not None else template.latitude if template is not None else None
    longitude = payload.longitude if payload.longitude is not None else template.longitude if template is not None else None

    return DeliveryAddressCreate(
        user_id=draft.user_id,
        mode=_require_delivery_value(mode, field_name="Delivery mode"),
        provider=_require_delivery_value(provider, field_name="Delivery provider"),
        country_code=_require_delivery_value(country_code, field_name="Delivery country"),
        name=optional_str(payload.name) or full_address,
        full_address=full_address,
        details=optional_str(payload.details) if "details" in fields else (template.details if template is not None else None),
        city=optional_str(payload.city) if "city" in fields else (template.city if template is not None else None),
        postal_code=optional_str(payload.postal_code) if "postal_code" in fields else (template.postal_code if template is not None else None),
        latitude=_require_delivery_value(latitude, field_name="Delivery latitude"),
        longitude=_require_delivery_value(longitude, field_name="Delivery longitude"),
        provider_reference=optional_str(payload.provider_reference) if "provider_reference" in fields else (template.provider_reference if template is not None else None),
    )
