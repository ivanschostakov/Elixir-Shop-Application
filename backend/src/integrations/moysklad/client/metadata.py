from typing import Any
from uuid import UUID
import httpx
from src.normalize import coerce_uuid, optional_str
from ..regions import moysklad_region_for_cdek, region_name_key
from .reference_cache import reference_rows
from .utils import _customer_order_attr_id, custom_entity_dictionary_id


_CHECKOUT_METHODS = ("delivery_method", "payment_method")


class MetadataMixin:
    async def get_organizations(self) -> list[dict[str, Any]]:
        return await self.get_all("/entity/organization")


    async def get_organization(self, organization_id: UUID | str) -> dict[str, Any] | None:
        normalized_id = coerce_uuid(organization_id)
        if normalized_id is None: return None

        async def load():
            try:
                row = await self._reference_entity("organization", normalized_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404: return None
                raise
            if not isinstance(row.get("name"), str) or not row["name"].strip():
                raise ValueError("Missing MoySklad organization name")
            return row

        return await self._references.read(("organization", normalized_id), load)


    async def _reference_entity(self, kind: str, entity_id: UUID) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.get(f"/entity/{kind}/{entity_id}")
        response.raise_for_status()
        row = response.json()
        if not isinstance(row, dict) or "errors" in row or coerce_uuid(row.get("id")) != entity_id:
            raise ValueError(f"Invalid MoySklad {kind} identity")
        return row


    async def get_currency_identity(self, currency_id: UUID | str) -> dict[str, Any]:
        """Identity for settlement checks; never cache an exchange rate."""
        normalized_id = coerce_uuid(currency_id)
        if normalized_id is None:
            raise ValueError("Invalid MoySklad currency ID")

        async def load():
            row = await self._reference_entity("currency", normalized_id)
            if not isinstance(row.get("isoCode"), str) or not row["isoCode"].strip() or not optional_str(row.get("code")):
                raise ValueError("Invalid MoySklad currency codes")
            return {key: row[key] for key in ("id", "isoCode", "code")}

        return await self._references.read(("currency-identity", normalized_id), load)


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
        key = region_name_key(moysklad_region_for_cdek(name) or name)
        if not key: return None
        matches = []
        # The region API may return the entire dictionary regardless of 'search'.
        for row in await self.get_all("/entity/region"):
            if region_name_key(row.get("name")) != key: continue
            if country_id and row.get("country"):
                href = (row["country"].get("meta") or {}).get("href", "")
                if coerce_uuid(href.rsplit("/", 1)[-1]) != country_id: continue
            matches.append(row)
        return matches[0] if len(matches) == 1 else None


    async def _document_metadata(self, kind: str) -> dict[str, Any]:
        async def load():
            http_client = await self.client()
            response = await http_client.get(f"/entity/{kind}/metadata")
            response.raise_for_status()
            data = response.json()
            reference_rows(data, "states")
            return data

        return await self._references.read(("metadata", kind), load, cacheable=lambda data: bool(data["states"]))


    async def get_customerorder_metadata(self) -> dict[str, Any]:
        return await self._document_metadata("customerorder")


    async def get_customerorder_states(self) -> list[dict[str, Any]]:
        return (await self.get_customerorder_metadata())["states"]


    async def get_invoiceout_metadata(self) -> dict[str, Any]:
        return await self._document_metadata("invoiceout")


    async def get_invoiceout_states(self) -> list[dict[str, Any]]:
        return (await self.get_invoiceout_metadata())["states"]


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
        rows = [row for row in await self.get_organizations() if not row.get("archived")]
        for name in names:
            key = optional_str(name)
            if not key: continue
            matches = [row for row in rows if (optional_str(row.get("name")) or "").casefold() == key.casefold()]
            if len(matches) > 1: raise ValueError("Ambiguous MoySklad organization name")
            if matches: return matches[0]
        return None


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
        async def load():
            return reference_rows(await self.get_page("/entity/customerorder/metadata/attributes", limit=limit))

        def has_bindings(rows):
            for key in _CHECKOUT_METHODS:
                matches = [row for row in rows if row.get("id") == _customer_order_attr_id(key)]
                if len(matches) != 1 or custom_entity_dictionary_id(matches[0]) is None:
                    return False
            return True

        return await self._references.read(("attributes", limit), load, cacheable=has_bindings)


    async def get_customerorder_customentity_values(self, attr_key: str, *, limit: int = 1000) -> list[dict[str, Any]]:
        attr_id = _customer_order_attr_id(attr_key)
        matches = [row for row in await self.get_customerorder_attribute_metadata(limit=limit) if row.get("id") == attr_id]
        if not matches: return []
        if len(matches) != 1: raise ValueError("Ambiguous MoySklad customer order attribute")
        custom_entity_id = custom_entity_dictionary_id(matches[0])
        if custom_entity_id is None: return []
        path = f"/entity/customentity/{custom_entity_id}"
        if attr_key not in _CHECKOUT_METHODS:
            return await self.get_all(path)
        return await self._references.read(("method-values", custom_entity_id), lambda: self.get_all(path))


    async def find_customerorder_customentity_value(self, attr_key: str, *names: str) -> dict[str, Any] | None:
        return self._find_named_row(await self.get_customerorder_customentity_values(attr_key), *names)
