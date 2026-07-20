import logging
import re

from decimal import Decimal
from typing import Any
from fastapi import HTTPException

from .constants import CF, PAID_STATUS_IDS, PIPELINE_ID, STATUS_IDS, STATUS_WORDS
from .payloads import build_contact_create_payload, build_contact_update_payload, build_lead_create_payload, build_lead_link_payload, build_lead_note_payload, build_order_lead_custom_fields
from .schemas.lead import LeadStatusUpdatePayload
from .transport import AmoCRMTransport
from .utils import extract_email_from_contact_obj, extract_phone_from_contact_obj, normalize_phone
from config import AMOCRM_ACCESS_TOKEN, AMOCRM_BASE_URL


class AsyncAmoCRM:
    @staticmethod
    def _normalize_order_code(value: str | int) -> str:
        code = str(value or "").strip()
        code = re.sub(r"^\s*заказ\s*", "", code, flags=re.IGNORECASE)
        code = re.sub(r"^\s*[№#]\s*", "", code)
        return code.strip()

    @classmethod
    def _order_lead_search(cls, value: str | int) -> tuple[str, re.Pattern[str]]:
        code = cls._normalize_order_code(value)
        needle = f"Заказ №{code}"
        pattern = re.compile(rf"Заказ\s*№\s*{re.escape(code)}(?=\s|$)", re.IGNORECASE)
        return needle, pattern

    def __init__(self, *, base_url: str | None = AMOCRM_BASE_URL, access_token: str | None = AMOCRM_ACCESS_TOKEN) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.transport = AmoCRMTransport(base_url=(base_url or "").strip(), access_token=access_token)
        self.PIPELINE_ID = PIPELINE_ID
        self.STATUS_IDS = STATUS_IDS
        self.STATUS_WORDS = STATUS_WORDS
        self.CF = CF
        self.PAID_STATUS_IDS = PAID_STATUS_IDS

    async def _request_with_auth_recovery(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        transport_call = getattr(self.transport, method.lower())
        return await transport_call(endpoint, **kwargs)

    async def _get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("POST", endpoint, **kwargs)

    async def _patch(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        return await self._request_with_auth_recovery("PATCH", endpoint, **kwargs)

    async def get_contact(self, contact_id: int) -> dict[str, Any] | None:
        try: return await self._get(f"/api/v4/contacts/{contact_id}")
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if isinstance(detail, dict) and detail.get("status_code") == 404: return None
            raise

    async def get_lead(self, lead_id: int) -> dict[str, Any]: return await self._get(f"/api/v4/leads/{lead_id}")

    async def search_contacts(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        if not query: return []
        data = await self._get("/api/v4/contacts", params={"query": query, "limit": limit})
        return (data.get("_embedded") or {}).get("contacts") or []

    async def create_contact(self, *, name: str, phone: str | None, email: str | None) -> dict[str, Any]:
        payload = build_contact_create_payload(name=name, phone=phone, email=email)
        data = await self._post("/api/v4/contacts", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("contacts") or [{}])[0]

    async def update_contact(self, contact_id: int, *, name: str | None = None, phone: str | None = None, email: str | None = None) -> dict[str, Any]:
        payload = build_contact_update_payload(contact_id=contact_id, name=name, phone=phone, email=email)
        data = await self._patch("/api/v4/contacts", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("contacts") or [{"id": contact_id}])[0]

    async def find_or_create_contact(self, *, lead_name: str, phone: str | None, email: str | None, contact_id: int | None = None) -> dict[str, Any]:
        normalized_phone = normalize_phone(phone)
        normalized_email = email.strip().lower() if email else None
        if contact_id:
            existing_contact = await self.get_contact(contact_id)
            if existing_contact: await self.update_contact(contact_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(contact_id); return refreshed_contact or existing_contact

        candidates: dict[int, dict[str, Any]] = {}
        queries = [candidate for candidate in [normalized_phone, phone, normalized_email] if candidate]
        for query in queries:
            for candidate in await self.search_contacts(query):
                raw_id = candidate.get("id")
                if raw_id: candidates[int(raw_id)] = candidate

        for candidate_id, candidate in candidates.items():
            full_contact = candidate if candidate.get("custom_fields_values") else await self.get_contact(candidate_id)
            if not full_contact: continue
            candidate_phone = extract_phone_from_contact_obj(full_contact)
            candidate_email = extract_email_from_contact_obj(full_contact)
            if normalized_phone and candidate_phone == normalized_phone: await self.update_contact(candidate_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(candidate_id); return refreshed_contact or full_contact
            if normalized_email and candidate_email == normalized_email: await self.update_contact(candidate_id, name=lead_name, phone=normalized_phone, email=normalized_email); refreshed_contact = await self.get_contact(candidate_id); return refreshed_contact or full_contact

        return await self.create_contact(name=lead_name, phone=normalized_phone, email=normalized_email)

    async def find_lead_by_order_number(self, order_number: str | int) -> dict[str, Any] | None:
        needle, pattern = self._order_lead_search(order_number)
        page, limit, max_pages = 1, 50, 20
        while page <= max_pages:
            data = await self._get("/api/v4/leads", params={"query": needle, "limit": limit, "page": page})
            leads = (data.get("_embedded") or {}).get("leads") or []
            if not leads: return None

            for lead in leads:
                name = lead.get("name") or ""
                if not pattern.search(name): continue
                pipeline_id = lead.get("pipeline_id")
                if pipeline_id is not None and pipeline_id != self.PIPELINE_ID: continue
                return lead

            page += 1
        return None

    async def create_lead(self, *, name: str, status_id: int, price: int | None = None, custom_fields: dict[int, object] | None = None) -> dict[str, Any]:
        payload = build_lead_create_payload(name=name, pipeline_id=self.PIPELINE_ID, status_id=status_id, price=price, custom_fields=custom_fields)
        data = await self._post("/api/v4/leads", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("leads") or [{}])[0]

    async def add_lead_note(self, lead_id: int, text: str) -> dict[str, Any]:
        payload = build_lead_note_payload(lead_id=lead_id, text=text)
        return await self._post("/api/v4/leads/notes", json=[self.transport.dump_payload(payload)])

    async def update_lead_status(self, lead_id: int, status_id: int) -> dict[str, Any]:
        payload = LeadStatusUpdatePayload(id=lead_id, pipeline_id=self.PIPELINE_ID, status_id=status_id)
        data = await self._patch("/api/v4/leads", json=[self.transport.dump_payload(payload)])
        return ((data.get("_embedded") or {}).get("leads") or [{"id": lead_id, "status_id": status_id}])[0]

    async def link_contact_to_lead(self, lead_id: int, contact_id: int) -> dict[str, Any]:
        payload = build_lead_link_payload(contact_id=contact_id)
        return await self._post(f"/api/v4/leads/{lead_id}/link", json=[self.transport.dump_payload(payload)])

    async def create_lead_with_contact_and_note(self, *, lead_name: str, price: int, address_str: str, phone: str, email: str | None, order_number: str, delivery_service: str, note_text: str, payment_method: str, tg_nick: str | None = None, status_id: int | None = None, delivery_sum: Decimal | float | int | None = None, contact_id: int | None = None) -> dict[str, Any]:
        lead_custom_fields = build_order_lead_custom_fields(cf=self.CF, address_str=address_str, order_number=order_number, delivery_service=delivery_service, payment_method=payment_method, tg_nick=tg_nick, delivery_sum=delivery_sum)
        lead = await self.create_lead(name=f"Заказ №{order_number} с Приложения", price=price, custom_fields=lead_custom_fields, status_id=status_id or self.STATUS_IDS["main"])
        lead_id = int(lead["id"])
        if contact_id: await self.link_contact_to_lead(lead_id, contact_id)
        await self.add_lead_note(lead_id, note_text)
        return lead

amocrm_client = AsyncAmoCRM()
