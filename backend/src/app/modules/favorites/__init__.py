from fastapi import APIRouter

from .router import favourite_products_router

favourites_router = APIRouter(prefix="/users/me/favorites", tags=["favorites"])
favourites_router.include_router(favourite_products_router)

favourites_query_router = APIRouter(prefix="/favorites", tags=["favorites"])
favourites_query_router.include_router(favourite_products_router)

__all__ = ["favourite_products_router", "favourites_router", "favourites_query_router"]
