from fastapi import APIRouter
from .cdek import cdek_router
from .geo import geo_router
from .yandex.router import yandex_router

delivery_router = APIRouter(prefix="/delivery", tags=["delivery"])
delivery_router.include_router(cdek_router)
delivery_router.include_router(geo_router)
delivery_router.include_router(yandex_router)
