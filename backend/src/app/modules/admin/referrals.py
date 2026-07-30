from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.admin import AdminContext, require_permission
from src.app.modules.admin.schemas.referrals import (
    AdminReferralAccrualRead,
    AdminReferralProfileRead,
    AdminRewardProgramChangePayload,
    AdminRewardProgramChangeRead,
    AdminReferralSummaryRead,
)
from src.app.services.admin import add_admin_audit
from src.app.services.referrals import select_reward_program
from src.app.services.admin.referrals import (
    list_accruals,
    list_profiles,
    referral_summary,
)
from src.database import get_db
from src.database.models import User

admin_referrals_router = APIRouter(prefix="/referrals", tags=["admin_referrals"])


@admin_referrals_router.get("/profiles", response_model=list[AdminReferralProfileRead], status_code=status.HTTP_200_OK)
async def list_referral_profiles(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("referrals.read"))) -> list[AdminReferralProfileRead]:
    rows = await list_profiles(db, limit=limit, offset=offset)
    return [AdminReferralProfileRead.model_validate(row) for row in rows]


@admin_referrals_router.get("/summary", response_model=AdminReferralSummaryRead, status_code=status.HTTP_200_OK)
async def get_referral_summary(db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("referrals.read"))) -> AdminReferralSummaryRead:
    return AdminReferralSummaryRead.model_validate(await referral_summary(db))


@admin_referrals_router.get(
    "/accruals",
    response_model=list[AdminReferralAccrualRead],
    status_code=status.HTTP_200_OK,
)
async def list_referral_accruals(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    accrual_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|approved|rejected)$",
    ),
    period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("referrals.read")),
) -> list[AdminReferralAccrualRead]:
    rows = await list_accruals(
        db,
        limit=limit,
        offset=offset,
        status=accrual_status,
        period=period,
    )
    return [AdminReferralAccrualRead.model_validate(row) for row in rows]


@admin_referrals_router.patch(
    "/profiles/{user_id}/program",
    response_model=AdminRewardProgramChangeRead,
    status_code=status.HTTP_200_OK,
)
async def change_referral_reward_program(
    user_id: int,
    payload: AdminRewardProgramChangePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(
        require_permission("customers.manage", write=True)
    ),
) -> AdminRewardProgramChangeRead:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Покупатель не найден / Customer was not found",
        )
    profile = await select_reward_program(
        db,
        user=user,
        program=payload.program,
        source="admin",
        force=True,
        reason=payload.reason,
        selected_by_admin_user_id=context.user.id,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="referral.program.change",
        entity_type="customer",
        entity_id=user.id,
        before={"reward_program": profile.reward_program_snapshot.get("previous_program")},
        after={
            "reward_program": profile.reward_program,
            "reason": payload.reason,
        },
    )
    await db.commit()
    return AdminRewardProgramChangeRead(
        user_id=user.id,
        reward_program=profile.reward_program,
        reward_program_selected_at=profile.reward_program_selected_at,
        reward_program_selection_source=profile.reward_program_selection_source or "admin",
    )
