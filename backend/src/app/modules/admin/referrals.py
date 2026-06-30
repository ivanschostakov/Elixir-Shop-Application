from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_admin_user
from src.app.modules.admin.schemas.referrals import (
    AdminReferralProfileRead,
)
from src.app.services.admin.referrals import (
    list_profiles,
)
from src.database import get_db
from src.database.models import User

admin_referrals_router = APIRouter(prefix="/admin/referrals", tags=["admin_referrals"])


@admin_referrals_router.get("/profiles", response_model=list[AdminReferralProfileRead], status_code=status.HTTP_200_OK)
async def list_referral_profiles(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> list[AdminReferralProfileRead]:
    rows = await list_profiles(db, limit=limit, offset=offset)
    return [AdminReferralProfileRead.model_validate(row) for row in rows]
