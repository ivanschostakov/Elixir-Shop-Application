from typing import Any
from uuid import UUID
from src.normalize import coerce_uuid, optional_str
from .utils import _customer_order_attr_id


class MetadataMixin:
    async def get_organizations(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/organization")


    async def get_organization(self, organization_id: UUID | str) -> dict[str, Any] | None:
        normalized_id = coerce_uuid(organization_id)
        if normalized_id is None: return None
        return await self._get_entity_by_id("organization", normalized_id)


    async def get_stores(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/store")


    async def get_countries(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/country")


    async def get_saleschannels(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/saleschannel")


    async def get_employees(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/employee")


    async def find_country_by_name_or_code(self, *values: str) -> dict[str, Any] | None:
        normalized_names = [name.casefold() for name in (optional_str(raw) for raw in values) if name]
        normalized_codes = [code.upper() for code in (optional_str(raw) for raw in values) if code]
        if not normalized_names and not normalized_codes: return None

        countries = await self.get_countries()
        for row in countries:
            code = optional_str(row.get("code"))
            if code and code.upper() in normalized_codes: return row

        for row in countries:
            row_name = optional_str(row.get("name"))
            if row_name and row_name.casefold() in normalized_names: return row

        return None


    async def find_region_by_name(self, name: str, *, country_id: UUID | None = None) -> dict[str, Any] | None:
        normalized_name = optional_str(name)
        if not normalized_name: return None

        data = await self.get_page("/entity/region", limit=200, search=normalized_name)
        rows = data.get("rows")
        if not isinstance(rows, list): return None

        normalized_key = normalized_name.casefold()
        candidate_rows = [row for row in rows if isinstance(row, dict)]
        if country_id is not None:
            filtered: list[dict[str, Any]] = []
            for row in candidate_rows:
                country_row = row.get("country")
                country_meta = country_row.get("meta") if isinstance(country_row, dict) else None
                country_href = optional_str(country_meta.get("href")) if isinstance(country_meta, dict) else None
                row_country_id = coerce_uuid(country_href.rsplit("/", 1)[-1]) if country_href else None
                if row_country_id == country_id: filtered.append(row)
            if filtered: candidate_rows = filtered

        exact_match = next((row for row in candidate_rows if optional_str(row.get("name")) and optional_str(row.get("name")).casefold() == normalized_key), None,)
        if exact_match is not None: return exact_match
        return candidate_rows[0] if candidate_rows else None


    async def get_customerorder_metadata(self) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.get("/entity/customerorder/metadata")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


    async def get_customerorder_states(self) -> list[dict[str, Any]]:
        states = (await self.get_customerorder_metadata()).get("states")
        if not isinstance(states, list): return []
        return [row for row in states if isinstance(row, dict)]


    async def get_invoiceout_metadata(self) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.get("/entity/invoiceout/metadata")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


    async def get_invoiceout_states(self) -> list[dict[str, Any]]:
        states = (await self.get_invoiceout_metadata()).get("states")
        if not isinstance(states, list): return []
        return [row for row in states if isinstance(row, dict)]


    async def get_organization_accounts(self, organization_id: UUID | str) -> list[dict[str, Any]]:
        data = await self.get_page(f"/entity/organization/{organization_id}", limit=1, expand="accounts")
        accounts = data.get("accounts")
        rows = accounts.get("rows") if isinstance(accounts, dict) else None
        if not isinstance(rows, list): return []
        return [row for row in rows if isinstance(row, dict)]


    @staticmethod
    def _find_named_row(rows: list[dict[str, Any]], *names: str) -> dict[str, Any] | None:
        normalized_names = [name.casefold() for name in (optional_str(raw) for raw in names) if name]
        if not normalized_names: return None
        matched: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_name = optional_str(row.get("name"))
            if not row_name: continue
            key = row_name.casefold()
            if key in normalized_names and key not in matched: matched[key] = row
        for key in normalized_names:
            row = matched.get(key)
            if row is not None: return row
        return None


    async def find_store_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_stores(), *names)


    async def find_organization_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_organizations(), *names)


    async def find_saleschannel_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_saleschannels(), *names)


    async def find_employee_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_employees(), *names)


    async def find_customerorder_state_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_customerorder_states(), *names)


    async def find_invoiceout_state_by_name(self, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_invoiceout_states(), *names)


    async def find_default_organization_account(self, organization_id: UUID | str, account_number: str | None = None) -> dict[str, Any] | None:
        accounts = await self.get_organization_accounts(organization_id)
        normalized_account_number = optional_str(account_number)
        if normalized_account_number:
            for row in accounts:
                if optional_str(row.get("accountNumber")) == normalized_account_number: return row
        for row in accounts:
            if row.get("isDefault") is True: return row
        return accounts[0] if accounts else None


    async def get_customerorder_attribute_metadata(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        data = await self.get_page("/entity/customerorder/metadata/attributes", limit=limit)
        rows = data.get("rows")
        if not isinstance(rows, list): return []
        return [row for row in rows if isinstance(row, dict)]


    async def get_customerorder_customentity_values(self, attr_key: str, *, limit: int = 1000) -> list[dict[str, Any]]:
        attr_id = _customer_order_attr_id(attr_key)
        attr_row = next((row for row in await self.get_customerorder_attribute_metadata(limit=limit) if optional_str(row.get("id")) == attr_id), None)
        if not isinstance(attr_row, dict): return []
        custom_entity_meta = attr_row.get("customEntityMeta")
        custom_entity_href = optional_str(custom_entity_meta.get("href")) if isinstance(custom_entity_meta, dict) else None
        if not custom_entity_href: return []
        custom_entity_id = custom_entity_href.rstrip("/").rsplit("/", 1)[-1]
        return await self.get_all(f"/entity/customentity/{custom_entity_id}")


    async def find_customerorder_customentity_value(self, attr_key: str, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_customerorder_customentity_values(attr_key), *names)
