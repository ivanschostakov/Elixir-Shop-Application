from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .env import _env


WORKING_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = WORKING_DIR / "logs"
MEDIA_DIR = WORKING_DIR / "media"
PRIVATE_MEDIA_DIR = WORKING_DIR / "private_media"
ATTACHMENTS_DIR = MEDIA_DIR / "attachments"
PRODUCTS_MEDIA_DIR = MEDIA_DIR / "products"
AVATARS_MEDIA_DIR = MEDIA_DIR / "avatars"
ORDERS_MEDIA_DIR = MEDIA_DIR / "orders"
REVIEWS_MEDIA_DIR = MEDIA_DIR / "reviews"
COMMUNITY_MEDIA_DIR = Path(
    _env("TELEGRAM_COMMUNITY_MEDIA_DIR", str(PRIVATE_MEDIA_DIR / "community"))
    or str(PRIVATE_MEDIA_DIR / "community")
)
TEMP_MEDIA_DIR = MEDIA_DIR / "temp"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
REVIEWS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
COMMUNITY_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

UFA_TZ = ZoneInfo("Asia/Yekaterinburg")


def ufa_now() -> datetime:
    return datetime.now(UFA_TZ)
