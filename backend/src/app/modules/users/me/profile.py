from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.auth.schemas.responses import AuthUserRead
from src.app.modules.users.me.schemas import PersonalDataUpdatePayload
from src.app.services.security import hash_password
from src.database import get_db
from src.database.crud.auth.user import get_user_by_email, get_user_by_username
from src.database.models import User

my_profile_router = APIRouter(prefix="/profile", tags=["my_profile"])


@my_profile_router.patch("/personal-data", response_model=AuthUserRead, status_code=status.HTTP_200_OK)
async def update_my_personal_data(
    payload: PersonalDataUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthUserRead:
    if payload.username is not None and payload.username != current_user.username:
        username_user = await get_user_by_username(db, payload.username)
        if username_user is not None and username_user.id != current_user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this username already exists")
        current_user.username = payload.username

    if payload.email is not None and payload.email != current_user.email:
        email_user = await get_user_by_email(db, payload.email)
        if email_user is not None and email_user.id != current_user.id and email_user.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
        current_user.email = payload.email
        current_user.is_verified = False

    if payload.name is not None:
        current_user.name = payload.name
    if payload.surname is not None:
        current_user.surname = payload.surname
    if "phone_number" in payload.model_fields_set:
        current_user.phone_number = payload.phone_number
    if payload.password is not None:
        current_user.password_hash = hash_password(payload.password)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this username or email already exists") from exc

    await db.refresh(current_user)
    return AuthUserRead.model_validate(current_user)
