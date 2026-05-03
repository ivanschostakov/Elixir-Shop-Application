from urllib.parse import quote as _quote

from .env import _int_env, _required_env


POSTGRES_DB = _required_env("POSTGRES_DB")
POSTGRES_USER = _required_env("POSTGRES_USER")
POSTGRES_PORT = _int_env("POSTGRES_PORT", 5432)
POSTGRES_HOST = _required_env("POSTGRES_HOST")
POSTGRES_PASSWORD = _required_env("POSTGRES_PASSWORD")

ASYNC_DB_URL = (
    "postgresql+asyncpg://"
    f"{_quote(POSTGRES_USER, safe='')}:{_quote(POSTGRES_PASSWORD, safe='')}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{_quote(POSTGRES_DB, safe='')}"
)
