from fastapi import APIRouter

from .ai_chat import ai_chat_router
from .avatar import avatar_router
from .basket import my_basket_router
from .benefits import my_benefits_router
from .order_drafts import my_order_drafts_router
from .orders import my_orders_router
from .push_tokens import push_tokens_router
from .profile import my_profile_router
from .recommendations import recommendations_router
from .referral_profile import my_referral_profile_router
from .search_queries import search_queries_router

me_router = APIRouter(prefix="/me", tags=["me"])
me_router.include_router(ai_chat_router)
me_router.include_router(avatar_router)
me_router.include_router(my_basket_router)
me_router.include_router(my_benefits_router)
me_router.include_router(my_order_drafts_router)
me_router.include_router(my_orders_router)
me_router.include_router(push_tokens_router)
me_router.include_router(my_profile_router)
me_router.include_router(recommendations_router)
me_router.include_router(my_referral_profile_router)
me_router.include_router(search_queries_router)

__all__ = ["me_router"]
