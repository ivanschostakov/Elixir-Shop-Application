from typing import Any
from uuid import UUID
import httpx
from src.integrations.moysklad.schemas import MoySkladCounterpartySyncResult
from src.normalize import coerce_uuid, normalize_email, normalize_phone, optional_str
from .common import logger


class CounterpartiesMixin:
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
        if normalize_phone(row.get("phone")) == normalized_phone: return True

        contactpersons = row.get("contactpersons")
        if isinstance(contactpersons, dict): contactpersons = contactpersons.get("rows")

        if not isinstance(contactpersons, list): return False

        for contactperson in contactpersons:
            if isinstance(contactperson, dict) and normalize_phone(contactperson.get("phone")) == normalized_phone: return True

        return False


    async def get_counterparty_by_phone(self, phone: str) -> dict[str, Any] | None:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone: return None

        data = await self.get_page("/entity/counterparty", limit=100, search=normalized_phone, expand="contactpersons")
        rows = data.get("rows")
        if not isinstance(rows, list): return None

        matches = [row for row in rows if isinstance(row, dict) and self._counterparty_phone_matches(row, normalized_phone)]
        # A truncated search or duplicate contact is not an identity decision.
        if len(rows) >= 100 or len({row.get("id") for row in matches}) > 1:
            logger.warning("MoySklad phone lookup is ambiguous; automatic linking skipped")
            return None
        return matches[0] if matches else None


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
        rows = data.get("rows")
        if not isinstance(rows, list): return None

        matches = [row for row in rows if isinstance(row, dict) and self._counterparty_email_matches(row, normalized_email)]
        if len(rows) >= 100 or len({row.get("id") for row in matches}) > 1:
            logger.warning("MoySklad email lookup is ambiguous; automatic linking skipped")
            return None
        return matches[0] if matches else None


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


    async def get_or_create_counterparty(self, *, existing_counterparty_id: UUID | None, external_code: str, sync_id: UUID, name: str, email: str | None, phone: str | None, actual_address: str | None) -> dict[str, Any]:
        normalized_external_code = optional_str(external_code)
        if not normalized_external_code: raise ValueError("Counterparty external_code is required")

        counterparty_data = await self._get_entity_by_id("counterparty", existing_counterparty_id) if existing_counterparty_id is not None else None
        if existing_counterparty_id is not None and counterparty_data is None: raise RuntimeError("Linked MoySklad counterparty is missing; manual relinking required")
        if counterparty_data is None: counterparty_data = await self._find_entity_by_external_code("counterparty", normalized_external_code)
        if counterparty_data is None: counterparty_data = await self._find_counterparty(normalized_external_code)

        payload: dict[str, Any] = {"name": name, "externalCode": normalized_external_code}
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        normalized_address = optional_str(actual_address)
        if normalized_email: payload["email"] = normalized_email
        if normalized_phone: payload["phone"] = normalized_phone
        if normalized_address: payload["actualAddress"] = normalized_address

        if counterparty_data is None:
            payload["syncId"] = str(sync_id)
            return await self._create_entity("counterparty", payload)

        counterparty_id = coerce_uuid(counterparty_data.get("id"))
        if counterparty_id is None: raise RuntimeError("MoySklad counterparty response is missing a valid id")
        # Order synchronization must not overwrite a shared customer's contacts
        # or replace another platform's externalCode with the application's ID.
        return counterparty_data


    async def resolve_or_sync_counterparty(self, *, existing_counterparty_id: UUID | None, external_code: str, sync_id: UUID, name: str, email: str | None, phone: str | None, actual_address: str | None) -> MoySkladCounterpartySyncResult:
        normalized_external_code = optional_str(external_code) or ""
        existing = await self._get_entity_by_id("counterparty", existing_counterparty_id) if existing_counterparty_id is not None else None
        if existing is None: existing = await self._find_entity_by_external_code("counterparty", normalized_external_code)
        if existing is None: existing = await self._find_counterparty(normalized_external_code)
        created = existing is None
        counterparty_data = await self.get_or_create_counterparty(existing_counterparty_id=existing_counterparty_id, external_code=normalized_external_code, sync_id=sync_id, name=name, email=email, phone=phone, actual_address=actual_address,)
        counterparty_id = coerce_uuid(counterparty_data.get("id"))
        if counterparty_id is None: raise RuntimeError("MoySklad counterparty response is missing a valid id")

        return MoySkladCounterpartySyncResult(counterparty_id=counterparty_id, external_code=normalized_external_code, created=created, updated=False,)
