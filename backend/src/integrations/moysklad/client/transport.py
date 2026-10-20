import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
import httpx
from fastapi import HTTPException
from config import MOY_SKLAD_BASE_URL, MOY_SKLAD_INCLUDED_PRODUCT_IDS, MOY_SKLAD_TIMEOUT_SECONDS, MOY_SKLAD_TOKEN, UFA_TZ
from src.normalize import coerce_uuid, optional_str
from .common import MOY_SKLAD_API_BASE_URL, logger
from .utils import moysklad_money


class TransportMixin:
    def __init__(self, token: str | None = MOY_SKLAD_TOKEN, base_url: str | None = MOY_SKLAD_BASE_URL, timeout: int = MOY_SKLAD_TIMEOUT_SECONDS, included_product_ids: list[str] | tuple[str, ...] | None = None,) -> None:
        self._token = optional_str(token) or ""
        self._base_url = (optional_str(base_url) or MOY_SKLAD_API_BASE_URL).rstrip("/")
        self._timeout = max(int(timeout), 1)
        configured_product_ids = (MOY_SKLAD_INCLUDED_PRODUCT_IDS if included_product_ids is None else included_product_ids)
        self._included_product_ids = {product_id for value in configured_product_ids if (product_id := coerce_uuid(value)) is not None}
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
        return moysklad_money(value)


    @staticmethod
    def _format_moment(moment: datetime) -> str:
        normalized = moment if moment.tzinfo is not None else moment.replace(tzinfo=UFA_TZ)
        return normalized.astimezone(UFA_TZ).strftime("%Y-%m-%d %H:%M:%S")


    async def client(self) -> httpx.AsyncClient:
        if not self.is_configured(): raise RuntimeError("MoySklad integration is not configured")
        if self._client and not self._client.is_closed: return self._client

        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(base_url=self._base_url, timeout=httpx.Timeout(self._timeout), limits=httpx.Limits(max_connections=20, max_keepalive_connections=10), headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json;charset=utf-8",
                    "Content-Type": "application/json;charset=utf-8",
                    "Accept-Encoding": "gzip",
                })
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
            if exc.response.status_code == 404: return None
            raise

        data = response.json()
        return data if isinstance(data, dict) else None


    async def _find_entity_by_external_code(self, entity_type: str, external_code: str) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        try:
            filtered = await self.get_page(f"/entity/{entity_type}", limit=100, filter=f"externalCode={external_code}")
            candidate_rows = filtered.get("rows")
            if isinstance(candidate_rows, list): rows.extend(row for row in candidate_rows if isinstance(row, dict))
        except httpx.HTTPStatusError as exc:
            if entity_type == "counterparty" or exc.response.status_code != 400: raise
            logger.debug("MoySklad %s filter lookup failed: %s", entity_type, exc)

        if not rows:
            searched = await self.get_page(f"/entity/{entity_type}", limit=100, search=external_code)
            candidate_rows = searched.get("rows")
            if isinstance(candidate_rows, list): rows.extend(row for row in candidate_rows if isinstance(row, dict))

        matches = [row for row in rows if optional_str(row.get("externalCode")) == external_code]
        if len({row.get("id") for row in matches}) > 1 or len(rows) >= 100:
            if entity_type == "counterparty": raise RuntimeError("Ambiguous MoySklad counterparty external code; manual review required")
            raise HTTPException(status_code=409, detail=f"Ambiguous MoySklad {entity_type} external code; manual review required")
        if matches: return matches[0]
        return None


    async def _create_entity(self, entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.post(f"/entity/{entity_type}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict): raise RuntimeError(f"MoySklad returned invalid {entity_type} create response")
        return data


    async def _update_entity(self, entity_type: str, entity_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        http_client = await self.client()
        response = await http_client.put(f"/entity/{entity_type}/{entity_id}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict): raise RuntimeError(f"MoySklad returned invalid {entity_type} update response")
        return data


    async def aclose(self) -> None:
        async with self._lock:
            if self._client and not self._client.is_closed: await self._client.aclose()
            self._client = None
