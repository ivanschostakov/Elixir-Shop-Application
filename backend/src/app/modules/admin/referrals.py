from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_admin_user
from src.app.modules.admin.schemas.referrals import (
    AdminReferralCommissionRead,
    AdminReferralDepositRead,
    AdminReferralProfileRead,
    AdminReferralPromoCodeRead,
    CommissionRunPayload,
    CommissionRunRead,
    InitialPurchaseBalancePayload,
    ManualDepositAdjustmentPayload,
    ManualDepositAdjustmentRead,
)
from src.app.services.admin.referrals import (
    create_manual_deposit_adjustment,
    list_commissions,
    list_deposits,
    list_profiles,
    list_promo_codes,
    run_commissions,
    set_initial_purchase_balance,
)
from src.database import get_db
from src.database.models import User

admin_referrals_router = APIRouter(prefix="/admin/referrals", tags=["admin_referrals"])


@admin_referrals_router.patch("/profiles/{user_id}/initial-balance", response_model=AdminReferralProfileRead, status_code=status.HTTP_200_OK)
async def set_referral_initial_purchase_balance(user_id: int, payload: InitialPurchaseBalancePayload, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> AdminReferralProfileRead: return AdminReferralProfileRead.model_validate(await set_initial_purchase_balance(db, user_id=user_id, amount=payload.amount))


@admin_referrals_router.post("/deposit-adjustments", response_model=ManualDepositAdjustmentRead, status_code=status.HTTP_201_CREATED)
async def create_manual_referral_deposit_adjustment(payload: ManualDepositAdjustmentPayload, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> ManualDepositAdjustmentRead: return ManualDepositAdjustmentRead.model_validate(await create_manual_deposit_adjustment(db, user_id=payload.user_id, amount=payload.amount, direction=payload.direction, currency=payload.currency, note=payload.note))


@admin_referrals_router.get("/profiles", response_model=list[AdminReferralProfileRead], status_code=status.HTTP_200_OK)
async def list_referral_profiles(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> list[AdminReferralProfileRead]:
    rows = await list_profiles(db, limit=limit, offset=offset)
    return [AdminReferralProfileRead.model_validate(row) for row in rows]


@admin_referrals_router.get("/promo-codes", response_model=list[AdminReferralPromoCodeRead], status_code=status.HTTP_200_OK)
async def list_referral_promo_codes(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> list[AdminReferralPromoCodeRead]:
    rows = await list_promo_codes(db, limit=limit, offset=offset)
    return [AdminReferralPromoCodeRead.model_validate(row) for row in rows]


@admin_referrals_router.get("/commissions", response_model=list[AdminReferralCommissionRead], status_code=status.HTTP_200_OK)
async def list_referral_commissions(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> list[AdminReferralCommissionRead]:
    rows = await list_commissions(db, limit=limit, offset=offset)
    return [AdminReferralCommissionRead.model_validate(row) for row in rows]


@admin_referrals_router.get("/deposits", response_model=list[AdminReferralDepositRead], status_code=status.HTTP_200_OK)
async def list_referral_deposits(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), user_id: int | None = Query(default=None, ge=1), db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> list[AdminReferralDepositRead]:
    rows = await list_deposits(db, limit=limit, offset=offset, user_id=user_id)
    return [AdminReferralDepositRead.model_validate(row) for row in rows]


@admin_referrals_router.post("/commissions/run", response_model=CommissionRunRead, status_code=status.HTTP_200_OK)
async def run_referral_commissions(payload: CommissionRunPayload, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)) -> CommissionRunRead:
    result: dict[str, Any] = await run_commissions(db, period_start=payload.period_start, period_end=payload.period_end, dry_run=payload.dry_run)
    return CommissionRunRead.model_validate(result)
