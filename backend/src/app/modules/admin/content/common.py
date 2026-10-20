from fastapi import APIRouter
from config import MEDIA_DIR


admin_content_router = APIRouter(tags=["admin_content"])


BANNERS_MEDIA_DIR = MEDIA_DIR / "banners"


BANNERS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)


ANALYTICS_TIMEZONE = "Asia/Yekaterinburg"


SUPPORTED_BANNER_ROUTES = {"/", "/discover", "/chat", "/basket", "/checkout", "/delivery", "/favorites", "/payment", "/profile", "/personal-data", "/profile-drafts", "/profile-history", "/contacts", "/requisites", "/public-offer",}
