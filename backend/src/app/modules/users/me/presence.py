from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import PresenceHeartbeatResponse
from src.database import get_db
from src.database.models import User

presence_router = APIRouter(prefix="/presence", tags=["presence"])


@presence_router.post(
    "/heartbeat",
    response_model=PresenceHeartbeatResponse,
    status_code=status.HTTP_200_OK,
)
async def heartbeat_my_presence(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PresenceHeartbeatResponse:
    seen_at = ufa_now()
    current_user.last_active_at = seen_at
    await db.commit()
    return PresenceHeartbeatResponse(seen_at=seen_at)


__all__ = ["presence_router"]
