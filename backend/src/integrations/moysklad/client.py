import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Any
from uuid import UUID

import httpx

from .rows import build_variant_rows, build_product_rows, EXCLUDED_PATHS
from .schemas import (
    MoySkladCatalogSyncStats,
    MoySkladCounterpartySyncResult,
    MoySkladCustomerOrderSyncResult,
    MoySkladInitialRelinkStats,
)

from config import MOY_SKLAD_BASE_URL, MOY_SKLAD_TIMEOUT_SECONDS, MOY_SKLAD_TOKEN, UFA_TZ
from src.normalize import coerce_uuid, normalize_email, normalize_phone, optional_str

logger = logging.getLogger(__name__)


class MoySkladClient:
    def __init__(self, token: str | None = MOY_SKLAD_TOKEN, base_url: str | None = MOY_SKLAD_BASE_URL, timeout: int = MOY_SKLAD_TIMEOUT_SECONDS) -> None:
        self._token = optional_str(token) or ""
        self._base_url = optional_str(base_url) or ""
        self._timeout = max(int(timeout), 1)
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool: return bool(self._token and self._base_url)

    @property
    def base_url(self) -> str:
        return self._base_url.rstrip("/")

    def entity_href(self, entity_type: str, entity_id: UUID | str) -> str:
        return f"{self.base_url}/entity/{entity_type}/{entity_id}"

    @staticmethod
    def _meta_payload(*, href: str, entity_type: str) -> dict[str, Any]:
        return {"meta": {"href": href, "type": entity_type, "mediaType": "application/json"}}

    @staticmethod
    def _money_to_minor(value: Decimal) -> int:
        return int((Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _format_moment(moment: datetime) -> str:
        normalized = moment if moment.tzinfo is not None else moment.replace(tzinfo=UFA_TZ)
        return normalized.astimezone(UFA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    async def client(self) -> httpx.AsyncClient:
        if not self.is_configured(): raise RuntimeError("MoySklad integration is not configured")
        if self._client and not self._client.is_closed: return self._client

        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=httpx.Timeout(self._timeout),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Accept": "application/json;charset=utf-8",
                        "Content-Type": "application/json;charset=utf-8",
                    },
                )
            return self._client

    async def get_page(self, path: str, *, limit: int = 100, offset: int = 0, **params: Any) -> dict[str, Any]:
        client = await self.client()
        response = await client.get(path, params={**params, "limit": limit, "offset": offset})
        response.raise_for_status()
        return response.json()

    async def get_all(self, path: str, **params: Any) -> list[dict[str, Any]]:
        rows, offset = [], 0
        while True:
            data = await self.get_page(path, offset=offset, **params)
            batch = data.get("rows", [])
            if not isinstance(batch, list): break
            rows.extend(row for row in batch if isinstance(row, dict))
            if len(batch) < 100: break
            offset += 100
        return rows

    async def _get_entity_by_id(self, entity_type: str, entity_id: UUID) -> dict[str, Any] | None:
        http_client = await self.client()
        try:
            response = await http_client.get(f"/entity/{entity_type}/{entity_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        data = response.json()
        return data if isinstance(data, dict) else None

    async def _find_entity_by_external_code(self, entity_type: str, external_code: str) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        try:
            filtered = await self.get_page(f"/entity/{entity_type}", limit=100, filter=f"externalCode={external_code}")
            candidate_rows = filtered.get("rows")
            if isinstance(candidate_rows, list):
                rows.extend(row for row in candidate_rows if isinstance(row, dict))
        except httpx.HTTPStatusError as exc:
            logger.debug("MoySklad %s filter lookup failed: %s", entity_type, exc)

        if not rows:
            try:
                searched = await self.get_page(f"/entity/{entity_type}", limit=100, search=external_code)
                candidate_rows = searched.get("rows")
                if isinstance(candidate_rows, list):
                    rows.extend(row for row in candidate_rows if isinstance(row, dict))
            except httpx.HTTPStatusError as exc:
                logger.debug("MoySklad %s search lookup failed: %s", entity_type, exc)

        for row in rows:
            if optional_str(row.get("externalCode")) == external_code:
                return row
        return None

    async def _create_entity(self, entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.post(f"/entity/{entity_type}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"MoySklad returned invalid {entity_type} create response")
        return data

    async def _update_entity(self, entity_type: str, entity_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.put(f"/entity/{entity_type}/{entity_id}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"MoySklad returned invalid {entity_type} update response")
        return data

    def build_customerorder_position(self, *, assortment_entity_type: str, assortment_id: UUID, quantity: int, unit_price: Decimal) -> dict[str, Any]:
        return {
            "assortment": self._meta_payload(
                href=self.entity_href(assortment_entity_type, assortment_id),
                entity_type=assortment_entity_type,
            ),
            "quantity": int(quantity),
            "price": self._money_to_minor(unit_price),
        }

    async def resolve_or_sync_counterparty(self, *, existing_counterparty_id: UUID | None, external_code: str, sync_id: UUID, name: str, email: str | None, phone: str | None, actual_address: str | None) -> MoySkladCounterpartySyncResult:
        counterparty_data: dict[str, Any] | None = None

        if existing_counterparty_id is not None:
            counterparty_data = await self._get_entity_by_id("counterparty", existing_counterparty_id)
        if counterparty_data is None:
            counterparty_data = await self._find_entity_by_external_code("counterparty", external_code)

        payload: dict[str, Any] = {"name": name, "externalCode": external_code}
        normalized_email = normalize_email(email)
        normalized_phone = normalize_phone(phone)
        normalized_address = optional_str(actual_address)
        if normalized_email:
            payload["email"] = normalized_email
        if normalized_phone:
            payload["phone"] = normalized_phone
        if normalized_address:
            payload["actualAddress"] = normalized_address

        created = False
        if counterparty_data is None:
            payload["syncId"] = str(sync_id)
            counterparty_data = await self._create_entity("counterparty", payload)
            created = True

        counterparty_id = coerce_uuid(counterparty_data.get("id"))
        if counterparty_id is None:
            raise RuntimeError("MoySklad counterparty response is missing a valid id")

        updated = False
        if not created:
            await self._update_entity("counterparty", counterparty_id, payload)
            updated = True

        return MoySkladCounterpartySyncResult(
            counterparty_id=counterparty_id,
            external_code=external_code,
            created=created,
            updated=updated,
        )

    async def resolve_or_sync_customerorder(self, *, existing_customerorder_id: UUID | None, external_code: str, sync_id: UUID, organization_id: UUID, counterparty_id: UUID, positions: list[dict[str, Any]], moment: datetime, description: str | None) -> MoySkladCustomerOrderSyncResult:
        customerorder_data: dict[str, Any] | None = None

        if existing_customerorder_id is not None:
            customerorder_data = await self._get_entity_by_id("customerorder", existing_customerorder_id)
        if customerorder_data is None:
            customerorder_data = await self._find_entity_by_external_code("customerorder", external_code)

        payload: dict[str, Any] = {
            "externalCode": external_code,
            "organization": self._meta_payload(
                href=self.entity_href("organization", organization_id),
                entity_type="organization",
            ),
            "agent": self._meta_payload(
                href=self.entity_href("counterparty", counterparty_id),
                entity_type="counterparty",
            ),
            "positions": positions,
            "moment": self._format_moment(moment),
        }
        normalized_description = optional_str(description)
        if normalized_description:
            payload["description"] = normalized_description

        created = False
        if customerorder_data is None:
            payload["syncId"] = str(sync_id)
            customerorder_data = await self._create_entity("customerorder", payload)
            created = True

        customerorder_id = coerce_uuid(customerorder_data.get("id"))
        if customerorder_id is None:
            raise RuntimeError("MoySklad customerorder response is missing a valid id")

        return MoySkladCustomerOrderSyncResult(
            customerorder_id=customerorder_id,
            external_code=external_code,
            created=created,
        )

    async def fetch_catalog_rows(self):
        logger.info("MoySklad catalog fetch started")
        products, variants, stocks = await asyncio.gather(
            self.get_all("/entity/product", filter="pathName!=Товары интернет-магазинов/elixirpeptide.ru"),
            self.get_all("/entity/variant", expand="product"),
            self.get_all("/report/stock/all"),
        )

        products = [p for p in products if p.get("pathName") not in EXCLUDED_PATHS]
        stats = MoySkladCatalogSyncStats()
        product_rows, products_by_code, products_by_id = build_product_rows(products, stats)
        variant_rows = build_variant_rows(variants, stocks, products_by_code, products_by_id, stats)
        stats.fetched_products = len(product_rows)
        stats.fetched_variants = len(variant_rows)
        logger.info("MoySklad catalog rows prepared products=%s variants=%s", stats.fetched_products, stats.fetched_variants)
        return product_rows, variant_rows, stats

    async def initial_relink_system_ids(self, _session, *, dry_run: bool = False) -> MoySkladInitialRelinkStats:
        logger.warning(
            "MoySklad initial relink is not implemented in the modular client; returning empty stats."
        )
        return MoySkladInitialRelinkStats(dry_run=dry_run)

    async def aclose(self) -> None:
        async with self._lock:
            if self._client and not self._client.is_closed: await self._client.aclose()
            self._client = None


moysklad_client = MoySkladClient()
def get_moysklad_client() -> MoySkladClient: return moysklad_client
