from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.services.security import decode_access_token
from src.database import get_db
from src.database.crud.auth.admin import is_admin_user
from src.database.crud.auth.user import get_user_by_id
from src.database.crud.auth.user_session import get_user_session_by_id
from src.database.models.auth.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized_exception(detail: str = "Could not validate credentials") -> HTTPException: return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})
def forbidden_exception(detail: str = "Admin privileges required") -> HTTPException: return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), db: AsyncSession = Depends(get_db)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":  raise unauthorized_exception()
    payload = decode_access_token(credentials.credentials)
    if payload is None or payload.get("type") != "access": raise unauthorized_exception()

    try:
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])

    except (KeyError, TypeError, ValueError): raise unauthorized_exception() from None

    user_session = await get_user_session_by_id(db, session_id)
    if user_session is None or user_session.user_id != user_id or user_session.purpose != "app" or user_session.revoked_at is not None: raise unauthorized_exception()
    if user_session.expires_at <= ufa_now(): raise unauthorized_exception("Session has expired")
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active: raise unauthorized_exception()
    return user


async def get_optional_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), db: AsyncSession = Depends(get_db)) -> User | None:
    if credentials is None: return None
    return await get_current_user(credentials=credentials, db=db)


async def get_current_admin_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    if not await is_admin_user(db, current_user.id): raise forbidden_exception()
    return current_user
