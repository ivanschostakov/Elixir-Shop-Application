from fastapi import APIRouter

from .analytics import admin_analytics_router
from .ai_chats import admin_ai_chats_router
from .auth import admin_auth_router
from .automation import admin_automation_router
from .catalog import admin_catalog_router
from .campaigns import admin_campaigns_router
from .content import admin_content_router
from .crm import admin_crm_router
from .customers import admin_customers_router
from .exports import admin_exports_router
from .integrations import admin_integrations_router
from .invitations import admin_invitations_router
from .leads import admin_leads_router
from .orders import admin_orders_router
from .overview import admin_overview_router
from .referrals import admin_referrals_router
from .settings import admin_settings_router
from .support import admin_support_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(admin_auth_router)
admin_router.include_router(admin_automation_router)
admin_router.include_router(admin_overview_router)
admin_router.include_router(admin_orders_router)
admin_router.include_router(admin_customers_router)
admin_router.include_router(admin_crm_router)
admin_router.include_router(admin_catalog_router)
admin_router.include_router(admin_content_router)
admin_router.include_router(admin_referrals_router)
admin_router.include_router(admin_campaigns_router)
admin_router.include_router(admin_analytics_router)
admin_router.include_router(admin_ai_chats_router)
admin_router.include_router(admin_support_router)
admin_router.include_router(admin_leads_router)
admin_router.include_router(admin_integrations_router)
admin_router.include_router(admin_invitations_router)
admin_router.include_router(admin_exports_router)
admin_router.include_router(admin_settings_router)

__all__ = ["admin_router"]
