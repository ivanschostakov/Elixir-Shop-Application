from datetime import datetime
from os import getenv
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo


def _env(name: str, default: str | None = None) -> str | None:
    value = getenv(name)
    if value is None or value == "": return default
    return value


def _required_env(name: str) -> str:
    value = _env(name)
    if value is None: raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _int_env(name: str, default: int | None = None) -> int:
    value = _env(name)
    if value is None:
        if default is None: raise RuntimeError(f"Missing required environment variable: {name}")
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = _env(name)
    if value is None: return default
    return float(value)


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None: return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


POSTGRES_DB = _required_env("POSTGRES_DB")
POSTGRES_USER = _required_env("POSTGRES_USER")
POSTGRES_PORT = _int_env("POSTGRES_PORT", 5432)
POSTGRES_HOST = _required_env("POSTGRES_HOST")
POSTGRES_PASSWORD = _required_env("POSTGRES_PASSWORD")

GEOSUGGEST_API_KEY = _env("GEOSUGGEST_API_KEY")
GEOSUGGEST_API_URL = _env("GEOSUGGEST_API_URL")
GEOCODE_API_URL = _env("GEOCODE_API_URL")
GEOCODE_API_KEY = _env("GEOCODE_API_KEY")

YANDEX_DELIVERY_BASE_URL = _env("YANDEX_DELIVERY_BASE_URL")
YANDEX_DELIVERY_TOKEN = _env("YANDEX_DELIVERY_TOKEN")
YANDEX_DELIVERY_WAREHOUSE_ID = _env("YANDEX_DELIVERY_WAREHOUSE_ID")

ASYNC_DB_URL = (
    "postgresql+asyncpg://"
    f"{quote(POSTGRES_USER, safe='')}:{quote(POSTGRES_PASSWORD, safe='')}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{quote(POSTGRES_DB, safe='')}"
)
API_BASE_URL = _env("API_BASE_URL")
PUBLIC_API_BASE_URL = _env("PUBLIC_API_BASE_URL")
REDIS_URL = _env("REDIS_URL")
WEBSITE_IDENTITY_ENDPOINT = _env("WEBSITE_IDENTITY_ENDPOINT")
WEBSITE_IDENTITY_TIMEOUT_SECONDS = _int_env("WEBSITE_IDENTITY_TIMEOUT_SECONDS", 15)
BITRIX_SYNC_API_ENDPOINT = _env("BITRIX_SYNC_API_ENDPOINT")
BITRIX_SYNC_API_APP_KEY = _env("BITRIX_SYNC_API_APP_KEY")
BITRIX_SYNC_API_APP_SECRET = _env("BITRIX_SYNC_API_APP_SECRET")
BITRIX_SYNC_API_TIMEOUT_SECONDS = _int_env("BITRIX_SYNC_API_TIMEOUT_SECONDS", 30)
APP_PAYMENT_RETURN_BASE_URL = _env("APP_PAYMENT_RETURN_BASE_URL")
EXPO_PUSH_API_URL = _env("EXPO_PUSH_API_URL", "https://exp.host/--/api/v2/push/send")
EXPO_PUSH_TIMEOUT_SECONDS = _float_env("EXPO_PUSH_TIMEOUT_SECONDS", 15)
SMTP_HOST = _env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _int_env("SMTP_PORT", 587)
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
SMTP_FROM_NAME = _env("SMTP_FROM_NAME", "ElixirPeptide")
EMAIL_VERIFICATION_CODE_TTL_MINUTES = _int_env("EMAIL_VERIFICATION_CODE_TTL_MINUTES", 10)
EMAIL_VERIFICATION_MAX_ATTEMPTS = _int_env("EMAIL_VERIFICATION_MAX_ATTEMPTS", 5)

WORKING_DIR = Path(__file__).parent
LOGS_DIR = WORKING_DIR / "logs"
MEDIA_DIR = WORKING_DIR / "media"
PRODUCTS_MEDIA_DIR = MEDIA_DIR / "products"
AVATARS_MEDIA_DIR = MEDIA_DIR / "avatars"
ORDERS_MEDIA_DIR = MEDIA_DIR / "orders"
TEMP_MEDIA_DIR = MEDIA_DIR / "temp"

CDEK_API_URL = _env("CDEK_API_URL")
CDEK_ACCOUNT = _env("CDEK_ACCOUNT")
CDEK_SECURE_PASSWORD = _env("CDEK_SECURE_PASSWORD")
CDEK_SENDER_CITY_CODE = _int_env("CDEK_SENDER_CITY_CODE", 256)
CDEK_SENDER_CITY = _env("CDEK_SENDER_CITY", "Уфа")
CDEK_SENDER_POSTAL_CODE = _env("CDEK_SENDER_POSTAL_CODE", "450078")
CDEK_SENDER_ADDRESS = _env("CDEK_SENDER_ADDRESS", "ул. Революционная, 98/1 блок А")
CDEK_SENDER_NAME = _env("CDEK_SENDER_NAME", "Elixir Peptide")
CDEK_SENDER_PHONE = _env("CDEK_SENDER_PHONE", "+79999999999")

AMOCRM_BASE_DOMAIN = _env("AMOCRM_BASE_DOMAIN")
AMOCRM_CLIENT_ID = _env("AMOCRM_CLIENT_ID")
AMOCRM_CLIENT_SECRET = _env("AMOCRM_CLIENT_SECRET")
AMOCRM_ACCESS_TOKEN = _env("AMOCRM_ACCESS_TOKEN")
AMOCRM_REFRESH_TOKEN = _env("AMOCRM_REFRESH_TOKEN")
AMOCRM_REDIRECT_URI = _env("AMOCRM_REDIRECT_URI")
AMOCRM_AUTH_CODE = _env("AMOCRM_AUTH_CODE")
AMOCRM_LOGIN_EMAIL = _env("AMOCRM_LOGIN_EMAIL")
AMOCRM_LOGIN_PASSWORD = _env("AMOCRM_LOGIN_PASSWORD")
AMOCRM_ACCOUNT_ID = _env("AMOCRM_ACCOUNT_ID", "19843447")
AMOCRM_PLAYWRIGHT_HEADLESS = _bool_env("AMOCRM_PLAYWRIGHT_HEADLESS")

INTELLECTMONEY_API_BASE = _env("INTELLECTMONEY_API_BASE", "https://merchant.intellectmoney.ru")
INTELLECTMONEY_BEARER_TOKEN = _env("INTELLECTMONEY_BEARER_TOKEN")
INTELLECTMONEY_SECRET_KEY = _env("INTELLECTMONEY_SECRET_KEY")
INTELLECTMONEY_SIGN_SECRET_KEY = _env("INTELLECTMONEY_SIGN_SECRET_KEY")
INTELLECTMONEY_SHOP_ID = _env("INTELLECTMONEY_SHOP_ID")
INTELLECTMONEY_IP_ADDRESS = _env("INTELLECTMONEY_IP_ADDRESS")

LOGS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
ORDERS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

UFA_TZ = ZoneInfo("Asia/Yekaterinburg")


def ufa_now() -> datetime:
    return datetime.now(UFA_TZ)


REFRESH_TOKEN_LIFETIME_DAYS = _int_env("REFRESH_TOKEN_LIFETIME_DAYS", 30)
JWT_ACCESS_EXPIRE_MINUTES = _int_env("JWT_ACCESS_EXPIRE_MINUTES", 15)
JWT_ACCESS_SECRET_KEY = _env("JWT_ACCESS_SECRET_KEY")
