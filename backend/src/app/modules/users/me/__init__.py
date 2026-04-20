from fastapi import APIRouter

from .avatar import avatar_router
from .basket import my_basket_router
from .benefits import my_benefits_router
from .website_identity import my_website_identity_router

me_router = APIRouter(prefix="/me", tags=["me"])
me_router.include_router(avatar_router)
me_router.include_router(my_basket_router)
me_router.include_router(my_benefits_router)
me_router.include_router(my_website_identity_router)

__all__ = ["me_router"]
