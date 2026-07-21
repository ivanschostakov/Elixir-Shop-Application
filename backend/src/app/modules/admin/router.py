from fastapi import APIRouter

from .auth import admin_auth_router
from .catalog import admin_catalog_router
from .content import admin_content_router
from .customers import admin_customers_router
from .integrations import admin_integrations_router
from .orders import admin_orders_router
from .overview import admin_overview_router
from .referrals import admin_referrals_router
from .settings import admin_settings_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(admin_auth_router)
admin_router.include_router(admin_overview_router)
admin_router.include_router(admin_orders_router)
admin_router.include_router(admin_customers_router)
admin_router.include_router(admin_catalog_router)
admin_router.include_router(admin_content_router)
admin_router.include_router(admin_referrals_router)
admin_router.include_router(admin_integrations_router)
admin_router.include_router(admin_settings_router)

__all__ = ["admin_router"]
