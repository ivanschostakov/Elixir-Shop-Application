import logging

import httpx

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel

from src.app.services.external_errors import external_service_http_exception
class AmoCRMTransport:
    def __init__(self, *, base_url: str, access_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.logger = logging.getLogger(self.__class__.__name__)

    def _ensure_config(self) -> None:
        missing = []
        if not self.base_url: missing.append("AMOCRM_BASE_URL")
        if not self.access_token: missing.append("AMOCRM_ACCESS_TOKEN")
        if missing: raise HTTPException(status_code=503, detail=f"Missing amoCRM config: {', '.join(missing)}")

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        self._ensure_config()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method=method, url=f"{self.base_url}{endpoint}", headers=headers, **kwargs)

        if response.status_code >= 400:
            raise external_service_http_exception(
                service="amocrm",
                operation=f"{method.upper()} {endpoint}",
                public_detail="amoCRM request failed",
                raw_detail={"status_code": response.status_code, "body": response.text},
            )
        if not response.text.strip(): return {}
        return response.json()

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]: return await self.request("GET", endpoint, **kwargs)
    async def post(self, endpoint: str, **kwargs: Any) -> dict[str, Any]: return await self.request("POST", endpoint, **kwargs)
    async def patch(self, endpoint: str, **kwargs: Any) -> dict[str, Any]: return await self.request("PATCH", endpoint, **kwargs)

    @staticmethod
    def dump_payload(model: BaseModel) -> dict[str, Any]: return model.model_dump(mode="json", exclude_none=True)
