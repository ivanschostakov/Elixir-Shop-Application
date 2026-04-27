from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.crud import delete_user_push_token, get_user_push_token_by_expo_token, upsert_user_push_token
from src.database.models import User
from src.database.schemas import UserPushTokenDelete, UserPushTokenDeleteResponse, UserPushTokenRead, UserPushTokenUpsert

push_tokens_router = APIRouter(prefix="/push-tokens", tags=["push-tokens"])


@push_tokens_router.post("", response_model=UserPushTokenRead, status_code=status.HTTP_200_OK)
async def upsert_my_push_token(
    payload: UserPushTokenUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPushTokenRead: return UserPushTokenRead.model_validate(await upsert_user_push_token(db, user_id=current_user.id, data=payload, commit=True))


@push_tokens_router.delete("", response_model=UserPushTokenDeleteResponse, status_code=status.HTTP_200_OK)
async def delete_my_push_token(
    payload: UserPushTokenDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPushTokenDeleteResponse:
    push_token = await get_user_push_token_by_expo_token(db, payload.expo_push_token)
    if push_token is None or push_token.user_id != current_user.id: return UserPushTokenDeleteResponse(ok=True)
    await delete_user_push_token(db, push_token, commit=True)
    return UserPushTokenDeleteResponse(ok=True)
