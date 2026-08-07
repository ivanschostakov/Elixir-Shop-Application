from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.admin import AdminContext, require_permission
from src.app.modules.admin.schemas.referrals import (
    AdminReferralAccrualRead,
    AdminOpeningBalanceUpdatePayload,
    AdminReferralProfileRead,
    AdminReferralSettlementRead,
    AdminReferralTransferPayload,
    AdminReferralTransferResult,
    AdminReferralSummaryRead,
    AdminRewardProgramUpdatePayload,
)
from src.app.services.admin.referrals import (
    list_accruals,
    list_profiles,
    list_settlements,
    mark_settlement_transferred,
    profile_row,
    referral_summary,
)
from src.app.services.referrals import (
    get_or_create_referral_profile,
    normalize_reward_program,
    refresh_profile_discount,
    select_reward_program,
)
from src.app.services.referrals.calculations import quantize_money
from src.database import get_db
from src.database.models import User
from src.integrations.bitrix_promo import BitrixPromoClient, BitrixPromoError, bitrix_promo_configured

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


@admin_referrals_router.get(
    "/settlements",
    response_model=list[AdminReferralSettlementRead],
    status_code=status.HTTP_200_OK,
)
async def list_referral_settlements(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("referrals.read")),
) -> list[AdminReferralSettlementRead]:
    rows = await list_settlements(
        db,
        limit=limit,
        offset=offset,
        period=period,
    )
    return [AdminReferralSettlementRead.model_validate(row) for row in rows]


@admin_referrals_router.post(
    "/settlements/transfer",
    response_model=AdminReferralTransferResult,
    status_code=status.HTTP_200_OK,
)
async def register_referral_transfer(
    payload: AdminReferralTransferPayload,
    db: AsyncSession = Depends(get_db),
    admin: AdminContext = Depends(require_permission("customers.manage", write=True)),
) -> AdminReferralTransferResult:
    result = await mark_settlement_transferred(
        db,
        beneficiary_bitrix_user_id=payload.beneficiary_bitrix_user_id,
        period=payload.period,
        currency=payload.currency,
        reference=payload.reference,
        admin_user_id=admin.user.id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No approved unsettled accruals were found; they may already "
                "have been credited to the deposit"
            ),
        )
    await db.commit()
    return AdminReferralTransferResult.model_validate(result)


@admin_referrals_router.post(
    "/profiles/{user_id}/program",
    response_model=AdminReferralProfileRead,
    status_code=status.HTTP_200_OK,
)
async def update_referral_program(
    user_id: int,
    payload: AdminRewardProgramUpdatePayload,
    db: AsyncSession = Depends(get_db),
    admin: AdminContext = Depends(require_permission("customers.manage", write=True)),
) -> AdminReferralProfileRead:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    profile = await select_reward_program(
        db,
        user=user,
        program=payload.program,
        source="admin",
        force=True,
        reason=payload.reason,
        selected_by_admin_user_id=admin.user.id,
    )
    await db.commit()
    return AdminReferralProfileRead.model_validate(profile_row(profile))


@admin_referrals_router.post(
    "/profiles/{user_id}/opening-balance",
    response_model=AdminReferralProfileRead,
    status_code=status.HTTP_200_OK,
)
async def update_referral_opening_balance(
    user_id: int,
    payload: AdminOpeningBalanceUpdatePayload,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("customers.manage", write=True)),
) -> AdminReferralProfileRead:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not bitrix_promo_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bitrix promo integration is not configured",
        )
    profile = await get_or_create_referral_profile(db, user=user)
    try:
        result = await BitrixPromoClient().set_opening_balance(
            amount=str(payload.amount),
            currency=payload.currency,
            bitrix_user_id=profile.bitrix_user_id,
            user_email=user.email,
        )
    except BitrixPromoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{error.message_ru} / {error.message_en}",
        ) from error
    profile.bitrix_user_id = int(result.get("user_id") or profile.bitrix_user_id or 0) or None
    profile.referral_discount_base_total = quantize_money(result.get("new_total"))
    refresh_profile_discount(
        profile,
        has_promo_code=(
            normalize_reward_program(profile.reward_program) == "partner"
            and bool(user.promo_code)
        ),
    )
    await db.commit()
    return AdminReferralProfileRead.model_validate(profile_row(profile))
