from typing import Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.external_errors import external_service_http_exception
from src.database.models.auth.user import User
from src.database.models.website.website_identity import WebsiteIdentity
from src.integrations.website_identity import WebsiteIdentityClient
from src.integrations.website_identity import WebsiteIdentityError

from .sync import resolve_user_for_website_login, sync_website_identity_payload_for_user


async def authenticate_website_identity(*, login: str, password: str, website_identity_client: WebsiteIdentityClient) -> dict[str, Any]:
    try: return await website_identity_client.authenticate(login=login, password=password)
    except WebsiteIdentityError as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED or exc.error_code == "invalid_credentials": raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid website credentials") from exc
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            raise external_service_http_exception(
                service="website_identity",
                operation="authenticate",
                public_detail="Website identity request was rejected",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                raw_detail=str(exc),
                exc=exc,
            ) from exc
        raise external_service_http_exception(
            service="website_identity",
            operation="authenticate",
            public_detail="Website identity service is temporarily unavailable",
            status_code=status.HTTP_502_BAD_GATEWAY,
            raw_detail=str(exc),
            exc=exc,
        ) from exc


async def login_with_website_identity(db: AsyncSession, *, login: str, password: str, website_identity_client: WebsiteIdentityClient) -> tuple[User, WebsiteIdentity]:
    website_payload = await authenticate_website_identity(login=login, password=password, website_identity_client=website_identity_client)
    user = await resolve_user_for_website_login(db, website_payload)
    website_identity = await sync_website_identity_payload_for_user(db, user=user, payload=website_payload)
    return user, website_identity


async def link_website_identity_to_user(db: AsyncSession, *, user: User, login: str, password: str, website_identity_client: WebsiteIdentityClient) -> WebsiteIdentity:
    website_payload = await authenticate_website_identity(login=login, password=password, website_identity_client=website_identity_client)
    return await sync_website_identity_payload_for_user(db, user=user, payload=website_payload)
