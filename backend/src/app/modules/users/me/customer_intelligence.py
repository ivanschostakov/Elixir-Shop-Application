from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CustomerIntelligenceSyncPayload, CustomerIntelligenceSyncResponse
from src.app.services.app_integrity import require_app_integrity
from src.app.services.customer_intelligence import ingest_customer_intelligence
from src.database import get_db
from src.database.models import User

customer_intelligence_router = APIRouter(prefix="/customer-intelligence", tags=["customer_intelligence"])


@customer_intelligence_router.post(
    "/sync",
    response_model=CustomerIntelligenceSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_my_customer_intelligence(
    payload: CustomerIntelligenceSyncPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("customer-intelligence:write")),
) -> CustomerIntelligenceSyncResponse:
    result = await ingest_customer_intelligence(db, user_id=current_user.id, payload=payload)
    return CustomerIntelligenceSyncResponse.model_validate(result)


__all__ = ["customer_intelligence_router"]
