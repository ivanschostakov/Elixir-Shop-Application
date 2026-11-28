from typing import Any
from uuid import UUID
import httpx
from src.integrations.moysklad.schemas import MoySkladCounterpartySyncResult
from src.normalize import coerce_uuid, normalize_email, normalize_phone, optional_str
from ..identity import CounterpartyReviewRequired, unique_contact


class CounterpartiesMixin:
    @staticmethod
    def _phone_identity(phone: Any) -> str | None:
        value = normalize_phone(phone)
        if not value: return None
        digits = value.removeprefix("+")
        if not digits.isascii() or not digits.isdigit() or not 7 <= len(digits) <= 15: return None
        return digits

    async def _find_counterparty(self, search: str) -> dict[str, Any] | None:
        normalized = optional_str(search)
        if not normalized: return None
        data = await self.get_page("/entity/counterparty", limit=100, search=normalized)
        rows = data.get("rows")
        if not isinstance(rows, list): return None
        matches = [row for row in rows if isinstance(row, dict) and optional_str(row.get("externalCode")) == normalized]
        if len(rows) >= 100 or len({row.get("id") for row in matches}) > 1: raise RuntimeError("Ambiguous MoySklad counterparty external code; manual review required")
        return matches[0] if matches else None


    @staticmethod
    def _counterparty_phone_matches(row: dict[str, Any], normalized_phone: str) -> bool:
        expected = CounterpartiesMixin._phone_identity(normalized_phone)
        if expected is None: return False
        if CounterpartiesMixin._phone_identity(row.get("phone")) == expected: return True

        contactpersons = row.get("contactpersons")
        if isinstance(contactpersons, dict): contactpersons = contactpersons.get("rows")

        if not isinstance(contactpersons, list): return False

        for contactperson in contactpersons:
            if isinstance(contactperson, dict) and CounterpartiesMixin._phone_identity(contactperson.get("phone")) == expected: return True

        return False


    async def get_counterparty_by_phone(self, phone: str) -> dict[str, Any] | None:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone: return None

        data = await self.get_page("/entity/counterparty", limit=100, search=normalized_phone, expand="contactpersons")
        return unique_contact(data, "телефону", lambda row: self._counterparty_phone_matches(row, normalized_phone))


    @staticmethod
    def _counterparty_email_matches(row: dict[str, Any], normalized_email: str) -> bool:
        if normalize_email(row.get("email")) == normalized_email: return True

        contactpersons = row.get("contactpersons")
        if isinstance(contactpersons, dict): contactpersons = contactpersons.get("rows")
        if not isinstance(contactpersons, list): return False

        return any(isinstance(contactperson, dict) and normalize_email(contactperson.get("email")) == normalized_email for contactperson in contactpersons)


    async def get_counterparty_by_email(self, email: str) -> dict[str, Any] | None:
        normalized_email = normalize_email(email)
        if not normalized_email: return None

        data = await self.get_page("/entity/counterparty", limit=100, search=normalized_email, expand="contactpersons",)
        return unique_contact(data, "email", lambda row: self._counterparty_email_matches(row, normalized_email))


    async def get_counterparty(self, counterparty_id: UUID, *, expand_bonus_program: bool = False,) -> dict[str, Any] | None:
        if not expand_bonus_program: return await self._get_entity_by_id("counterparty", counterparty_id)

        http_client = await self.client()
        try:
            response = await http_client.get(f"/entity/counterparty/{counterparty_id}", params={"expand": "bonusProgram"},)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404: return None
            raise

        data = response.json()
        return data if isinstance(data, dict) else None


    async def update_counterparty_email(self, counterparty_id: UUID, email: str) -> None:
        normalized_email = normalize_email(email)
        if not normalized_email: return
        await self._update_entity("counterparty", counterparty_id, {"email": normalized_email})


    async def _resolve_counterparty(self, *, existing_counterparty_id: UUID | None, external_code: str, sync_id: UUID, name: str, email: str | None, phone: str | None, actual_address: str | None, initial_attributes: list[dict] | None = None):
        normalized_external_code = optional_str(external_code)
        if not normalized_external_code: raise ValueError("Counterparty external_code is required")

        counterparty_data = await self._get_entity_by_id("counterparty", existing_counterparty_id) if existing_counterparty_id is not None else None
        if existing_counterparty_id is not None and counterparty_data is None: raise RuntimeError("Linked MoySklad counterparty is missing; manual relinking required")
        if counterparty_data is None: counterparty_data = await self._find_entity_by_external_code("counterparty", normalized_external_code)

        payload: dict[str, Any] = {"name": name, "externalCode": normalized_external_code}
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        normalized_address = optional_str(actual_address)
        if normalized_email: payload["email"] = normalized_email
        if normalized_phone: payload["phone"] = normalized_phone
        if normalized_address: payload["actualAddress"] = normalized_address

        if existing_counterparty_id is None:
            for field, value, lookup in (("email", normalized_email, self.get_counterparty_by_email),
                                         ("телефону", normalized_phone, self.get_counterparty_by_phone)):
                if value:
                    contact = await lookup(value)
                    if contact and (not counterparty_data or contact["id"] != counterparty_data.get("id")):
                        raise CounterpartyReviewRequired(field, [contact, counterparty_data])

        if counterparty_data is None:
            payload["syncId"] = str(sync_id)
            if initial_attributes is not None:
                payload["attributes"] = initial_attributes
            return await self._create_entity("counterparty", payload), True

        counterparty_id = coerce_uuid(counterparty_data.get("id"))
        if counterparty_id is None: raise RuntimeError("MoySklad counterparty response is missing a valid id")
        # Order synchronization must not overwrite a shared customer's contacts
        # or replace another platform's externalCode with the application's ID.
        return counterparty_data, False

    async def get_or_create_counterparty(self, **kwargs):
        row, _ = await self._resolve_counterparty(**kwargs)
        return row


    async def resolve_or_sync_counterparty(self, *, existing_counterparty_id: UUID | None, external_code: str, sync_id: UUID, name: str, email: str | None, phone: str | None, actual_address: str | None, initial_attributes: list[dict] | None = None) -> MoySkladCounterpartySyncResult:
        normalized_external_code = optional_str(external_code) or ""
        counterparty_data, created = await self._resolve_counterparty(existing_counterparty_id=existing_counterparty_id,
            external_code=normalized_external_code, sync_id=sync_id, name=name, email=email, phone=phone,
            actual_address=actual_address, initial_attributes=initial_attributes)
        counterparty_id = coerce_uuid(counterparty_data.get("id"))
        if counterparty_id is None: raise RuntimeError("MoySklad counterparty response is missing a valid id")

        return MoySkladCounterpartySyncResult(counterparty_id=counterparty_id, external_code=normalized_external_code, created=created, updated=False,)
