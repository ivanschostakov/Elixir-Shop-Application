from fastapi import APIRouter

from .modules import (
    auth_router,
    app_integrity_router,
    delivery_router,
    favourites_query_router,
    favourites_router,
    payments_router,
    product_categories_router,
    products_router,
    requisites_router,
    users_router,
    webhooks_router,
)

api_router = APIRouter(prefix="/api")
v1_router = APIRouter(prefix="/v1")

v1_router.include_router(auth_router)
v1_router.include_router(app_integrity_router)
v1_router.include_router(product_categories_router)
v1_router.include_router(products_router)
v1_router.include_router(requisites_router)
v1_router.include_router(favourites_router)
v1_router.include_router(favourites_query_router)
v1_router.include_router(users_router)
v1_router.include_router(delivery_router)
v1_router.include_router(payments_router)
v1_router.include_router(webhooks_router)
api_router.include_router(v1_router)

__all__ = [
    "api_router",
    "v1_router",
    "auth_router",
    "app_integrity_router",
    "product_categories_router",
    "products_router",
    "requisites_router",
    "favourites_router",
    "favourites_query_router",
    "payments_router",
    "users_router",
    "webhooks_router",
]
