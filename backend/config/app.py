from .env import _csv_env, _env


API_BASE_URL = _env("API_BASE_URL")
PUBLIC_API_BASE_URL = _env("PUBLIC_API_BASE_URL")
CORS_ALLOWED_ORIGINS = _csv_env(
    "CORS_ALLOWED_ORIGINS",
    "https://api-elixirshop.devsivanschostakov.org",
)

REDIS_URL = _env("REDIS_URL")
