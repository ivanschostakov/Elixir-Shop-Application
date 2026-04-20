from fastapi import APIRouter, Depends

from src.app.modules.auth.dependencies import get_current_user

from .me import me_router

users_router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])
users_router.include_router(me_router)

__all__ = ["users_router"]
