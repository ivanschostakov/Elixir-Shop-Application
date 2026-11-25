import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import APP_INTEGRITY_ANDROID_CLOUD_PROJECT_NUMBER
from src.app.modules.auth.dependencies import get_current_user
from src.app.services.app_integrity import create_app_integrity_challenge, register_ios_app_attest_key as register_ios_app_attest_key_service
from src.app.services.app_integrity.service import app_integrity_exempt_for_user, preverify_ios_app_attest_assertion
from src.database import get_db
from src.database.models import User
from .schemas import AppIntegrityChallengeRead, AppIntegrityChallengeCreate, AppIntegrityConfigRead, IosAppAttestRegisterRead, IosAppAttestRegisterPayload
from .schemas import IosAppAttestVerifyPayload, IosAppAttestVerifyRead

app_integrity_router = APIRouter(prefix="/app-integrity", tags=["app-integrity"])


@app_integrity_router.get("/config", response_model=AppIntegrityConfigRead, status_code=status.HTTP_200_OK)
async def get_app_integrity_config() -> AppIntegrityConfigRead:
    return AppIntegrityConfigRead(
        android_cloud_project_number=APP_INTEGRITY_ANDROID_CLOUD_PROJECT_NUMBER,
    )


@app_integrity_router.post("/ios/challenge", response_model=AppIntegrityChallengeRead, status_code=status.HTTP_200_OK)
async def create_ios_app_attest_challenge(payload: AppIntegrityChallengeCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> AppIntegrityChallengeRead:
    if payload.purpose == "assertion" and not payload.action: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="action is required for assertion challenges")
    challenge = await create_app_integrity_challenge(db, user_id=current_user.id, platform="ios", purpose=payload.purpose, action=payload.action if payload.purpose == "assertion" else None)
    return AppIntegrityChallengeRead(challenge=challenge.challenge)


@app_integrity_router.post("/ios/register", response_model=IosAppAttestRegisterRead, status_code=status.HTTP_200_OK)
async def register_ios_app_attest_key(payload: IosAppAttestRegisterPayload, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> IosAppAttestRegisterRead:
    if app_integrity_exempt_for_user(current_user):
        # Existing clients still register before sending a protected request.
        return IosAppAttestRegisterRead(key_id=payload.key_id, environment="exempt")
    key = await register_ios_app_attest_key_service(db, user_id=current_user.id, key_id=payload.key_id, challenge=payload.challenge, attestation_object=payload.attestation_object)
    return IosAppAttestRegisterRead(key_id=key.key_id, environment=key.environment)


@app_integrity_router.post("/ios/verify", response_model=IosAppAttestVerifyRead)
async def preverify_ios_assertion(payload: IosAppAttestVerifyPayload, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> IosAppAttestVerifyRead:
    if app_integrity_exempt_for_user(current_user):
        # This acknowledgement is not a verified grant and is never persisted.
        return IosAppAttestVerifyRead(grant="exempt:" + secrets.token_urlsafe(32))
    grant = await preverify_ios_app_attest_assertion(db, user_id=current_user.id, key_id=payload.key_id, assertion=payload.assertion, challenge=payload.challenge, action=payload.action)
    return IosAppAttestVerifyRead(grant=grant.challenge)
