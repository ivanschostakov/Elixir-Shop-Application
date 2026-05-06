from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas.referrals import (
    ReferrerCodeAttachPayload,
    ReferrerCodeCheckPayload,
    ReferrerCodeCheckRead,
    ReferralProfileRead,
)
from src.app.services.referrals import attach_referrer_code, check_referrer_code, get_referral_profile_summary
from src.database import get_db
from src.database.models import User

my_referral_profile_router = APIRouter(prefix="/referral-profile", tags=["my_referral_profile"])


@my_referral_profile_router.get("", response_model=ReferralProfileRead, status_code=status.HTTP_200_OK)
async def get_my_referral_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReferralProfileRead:
    summary = await get_referral_profile_summary(db, user=current_user)
    await db.commit()
    return ReferralProfileRead.model_validate(summary)


@my_referral_profile_router.post("/referrer-code/check", response_model=ReferrerCodeCheckRead, status_code=status.HTTP_200_OK)
async def check_my_referrer_code(
    payload: ReferrerCodeCheckPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReferrerCodeCheckRead:
    result = await check_referrer_code(db, user=current_user, code=payload.code)
    return ReferrerCodeCheckRead.model_validate(result)


@my_referral_profile_router.post("/referrer-code", response_model=ReferralProfileRead, status_code=status.HTTP_200_OK)
async def attach_my_referrer_code(
    payload: ReferrerCodeAttachPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReferralProfileRead:
    await attach_referrer_code(db, user=current_user, code=payload.code, confirmed=payload.confirmed)
    summary = await get_referral_profile_summary(db, user=current_user)
    await db.commit()
    return ReferralProfileRead.model_validate(summary)
