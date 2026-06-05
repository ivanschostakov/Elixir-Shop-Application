import logging

import httpx

from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from fastapi import HTTPException
from pydantic import BaseModel

from src.app.services.external_errors import external_service_http_exception
from .schemas.oauth import AuthorizationCodeRequest, OAuthTokenResponse, RefreshTokenRequest


class AmoCRMTransport:
    def __init__(self, *, base_domain: str, client_id: str, client_secret: str, redirect_uri: str, access_token: str | None = None, refresh_token: str | None = None, save_tokens_callback: Callable[[dict[str, str]], None] | None = None) -> None:
        self.base_domain = base_domain.strip()
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = datetime.now(UTC) + timedelta(minutes=10)
        self._save_tokens_callback = save_tokens_callback
        self.logger = logging.getLogger(self.__class__.__name__)

    def _ensure_config(self) -> None:
        missing = []
        if not self.base_domain: missing.append("AMOCRM_BASE_DOMAIN")
        if not self.client_id: missing.append("AMOCRM_CLIENT_ID")
        if not self.client_secret: missing.append("AMOCRM_CLIENT_SECRET")
        if not self.redirect_uri: missing.append("AMOCRM_REDIRECT_URI")
        if missing: raise HTTPException(status_code=503, detail=f"Missing amoCRM config: {', '.join(missing)}")

    @staticmethod
    def _redact_oauth_payload(payload: dict[str, Any]) -> dict[str, Any]:
        redacted = dict(payload)
        for key in ("client_secret", "code", "refresh_token"):
            if redacted.get(key):
                redacted[key] = "<redacted>"
        return redacted

    async def _request_token(self, payload: AuthorizationCodeRequest | RefreshTokenRequest) -> OAuthTokenResponse:
        self._ensure_config()
        url = f"https://{self.base_domain}/oauth2/access_token"
        raw_payload = payload.model_dump(mode="json")
        safe_payload = self._redact_oauth_payload(raw_payload)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=raw_payload)
        if response.status_code >= 400:
            self.logger.error(
                "AmoCRM OAuth token request failed | method=POST | url=%s | json=%s | status=%s | content_type=%s | response=%s",
                url,
                safe_payload,
                response.status_code,
                response.headers.get("content-type"),
                response.text[:1000],
            )
            raise external_service_http_exception(
                service="amocrm",
                operation=f"oauth:{payload.grant_type}",
                public_detail="amoCRM authentication failed",
                raw_detail={"status_code": response.status_code, "body": response.text, "request": {"method": "POST", "url": url, "json": safe_payload}},
            )
        data = OAuthTokenResponse.model_validate(response.json())
        self.access_token = data.access_token
        self.refresh_token = data.refresh_token
        self.expires_at = datetime.now(UTC) + timedelta(seconds=data.expires_in or 3600)
        if self._save_tokens_callback: self._save_tokens_callback({"AMOCRM_ACCESS_TOKEN": self.access_token, "AMOCRM_REFRESH_TOKEN": self.refresh_token})
        return data

    async def authorize_with_code(self, code: str) -> OAuthTokenResponse:
        return await self._request_token(AuthorizationCodeRequest(client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.redirect_uri, code=code))

    async def refresh(self) -> OAuthTokenResponse:
        if not self.refresh_token: raise HTTPException(status_code=503, detail="Missing amoCRM refresh token")
        return await self._request_token(RefreshTokenRequest(client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.redirect_uri, refresh_token=self.refresh_token))

    async def ensure_token_valid(self) -> None:
        if not self.access_token or datetime.now(UTC) >= self.expires_at: await self.refresh()

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        await self.ensure_token_valid()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method=method, url=f"https://{self.base_domain}{endpoint}", headers=headers, **kwargs)
            if response.status_code in {401, 403}:
                await self.refresh()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(method=method, url=f"https://{self.base_domain}{endpoint}", headers=headers, **kwargs)

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
