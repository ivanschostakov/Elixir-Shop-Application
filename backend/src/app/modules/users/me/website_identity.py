from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.auth.schemas.website import WebsiteIdentityLoginPayload
from src.app.services.website_identities.service import link_website_identity_to_user
from src.integrations.website_identity import WebsiteIdentityClient, get_website_identity_client
from src.database import get_db
from src.database.crud.website.website_identity import get_website_identity_by_user_id
from src.database.models.auth.user import User
from src.database.schemas.website.website_identity import WebsiteIdentityRead

my_website_identity_router = APIRouter(prefix="/website-identity", tags=["my_website_identity"])


@my_website_identity_router.get("", response_model=WebsiteIdentityRead, status_code=status.HTTP_200_OK)
async def get_my_website_identity(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> WebsiteIdentityRead:
    website_identity = await get_website_identity_by_user_id(db, current_user.id)
    if website_identity is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Website identity not found")
    return WebsiteIdentityRead.model_validate(website_identity)


@my_website_identity_router.post("/link", response_model=WebsiteIdentityRead, status_code=status.HTTP_200_OK)
async def link_my_website_identity(
    payload: WebsiteIdentityLoginPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    website_identity_client: WebsiteIdentityClient = Depends(get_website_identity_client),
) -> WebsiteIdentityRead:
    website_identity = await link_website_identity_to_user(db, user=current_user, login=payload.login, password=payload.password, website_identity_client=website_identity_client)
    return WebsiteIdentityRead.model_validate(website_identity)
