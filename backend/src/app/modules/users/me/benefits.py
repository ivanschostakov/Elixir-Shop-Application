from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas.benefits import BenefitCheckPayload, BenefitCheckRead
from src.app.services.benefits.service import resolve_benefits_for_user
from src.database import get_db
from src.database.models.auth.user import User

my_benefits_router = APIRouter(prefix="/benefits", tags=["my_benefits"])


@my_benefits_router.post("/check", response_model=BenefitCheckRead, status_code=status.HTTP_200_OK)
async def check_my_benefits(payload: BenefitCheckPayload, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BenefitCheckRead:
    resolved = await resolve_benefits_for_user(
        db,
        user=current_user,
        entered_code=payload.code,
        subtotal=payload.subtotal,
        currency=payload.currency,
        requested_bonus_amount=payload.requested_bonus_amount,
    )
    return BenefitCheckRead.model_validate(resolved)
