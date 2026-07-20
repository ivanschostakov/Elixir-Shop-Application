from fastapi import APIRouter

from .modules.admin import admin_referrals_router
from .modules.app_integrity import app_integrity_router
from .modules.app_version import app_version_router
from .modules.auth.router import auth_router
from .modules.banners import banners_router
from .modules.community_media import community_media_router
from .modules.delivery import delivery_router
from .modules.favorites import favourites_query_router, favourites_router
from .modules.guest import guest_router
from .modules.health import health_router
from .modules.payments import payments_router
from .modules.product_categories import product_categories_router
from .modules.products import products_router
from .modules.requisites import requisites_router
from .modules.users import users_router
from .modules.webhooks import webhooks_router

api_router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/v1")

v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(admin_referrals_router)
v1_router.include_router(app_integrity_router)
v1_router.include_router(app_version_router)
v1_router.include_router(banners_router)
v1_router.include_router(community_media_router)
v1_router.include_router(product_categories_router)
v1_router.include_router(products_router)
v1_router.include_router(requisites_router)
v1_router.include_router(favourites_router)
v1_router.include_router(favourites_query_router)
v1_router.include_router(guest_router)
v1_router.include_router(users_router)
v1_router.include_router(delivery_router)
v1_router.include_router(payments_router)
v1_router.include_router(webhooks_router)
api_router.include_router(v1_router)

__all__ = [
    "api_router",
    "v1_router",
    "auth_router",
    "banners_router",
    "community_media_router",
    "app_integrity_router",
    "app_version_router",
    "admin_referrals_router",
    "health_router",
    "product_categories_router",
    "products_router",
    "requisites_router",
    "favourites_router",
    "favourites_query_router",
    "guest_router",
    "payments_router",
    "users_router",
    "webhooks_router",
]
