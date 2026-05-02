from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.services.app_integrity import create_app_integrity_challenge, register_ios_app_attest_key as register_ios_app_attest_key_service
from src.database import get_db
from src.database.models import User
from .schemas import AppIntegrityChallengeRead, AppIntegrityChallengeCreate, IosAppAttestRegisterRead, IosAppAttestRegisterPayload

app_integrity_router = APIRouter(prefix="/app-integrity", tags=["app-integrity"])


@app_integrity_router.post("/ios/challenge", response_model=AppIntegrityChallengeRead, status_code=status.HTTP_200_OK)
async def create_ios_app_attest_challenge(
    payload: AppIntegrityChallengeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppIntegrityChallengeRead:
    if payload.purpose == "assertion" and not payload.action:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action is required for assertion challenges",
        )

    challenge = await create_app_integrity_challenge(
        db,
        user_id=current_user.id,
        platform="ios",
        purpose=payload.purpose,
        action=payload.action if payload.purpose == "assertion" else None,
    )
    return AppIntegrityChallengeRead(challenge=challenge.challenge)


@app_integrity_router.post("/ios/register", response_model=IosAppAttestRegisterRead, status_code=status.HTTP_200_OK)
async def register_ios_app_attest_key(
    payload: IosAppAttestRegisterPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IosAppAttestRegisterRead:
    key = await register_ios_app_attest_key_service(
        db,
        user_id=current_user.id,
        key_id=payload.key_id,
        challenge=payload.challenge,
        attestation_object=payload.attestation_object,
    )
    return IosAppAttestRegisterRead(key_id=key.key_id, environment=key.environment)
