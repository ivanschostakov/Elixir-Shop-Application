import json
import logging

from typing import Any
from redis.asyncio import Redis

from config import REDIS_URL
from .constants import CACHE_NAMESPACE_DEFAULT_VERSION, CACHE_NAMESPACE_KEY_PREFIX
from .helpers import jitter_ttl_seconds

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, redis_url: str | None = REDIS_URL) -> None:
        self._redis_url = (redis_url or "").strip()
        self._client: Redis | None = None
        self._connected = False

    @property
    def client(self) -> Redis | None:
        return self._client

    async def connect(self) -> None:
        if self._client is not None and self._connected: return
        try:
            self._client = Redis.from_url(self._redis_url, decode_responses=True)
            await self._client.ping()
            self._connected = True
            logger.info("cache_connected")

        except Exception:
            self._connected = False
            self._client = None
            logger.exception("cache_connect_error")

    async def close(self) -> None:
        if self._client is None: return
        try: await self._client.aclose()
        except Exception: logger.exception("cache_close_error")
        finally:
            self._client = None
            self._connected = False

    async def get_json(self, key: str, *, key_prefix: str) -> Any | None:
        if self._client is None: return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                logger.info("cache_miss prefix=%s", key_prefix)
                return None

            logger.info("cache_hit prefix=%s", key_prefix)
            return json.loads(raw)

        except Exception:
            logger.exception("cache_get_error prefix=%s", key_prefix)
            return None

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int, key_prefix: str) -> None:
        if self._client is None: return
        try:
            ttl = jitter_ttl_seconds(ttl_seconds)
            payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            await self._client.set(key, payload, ex=ttl)
            logger.info("cache_set prefix=%s ttl=%s", key_prefix, ttl)

        except Exception: logger.exception("cache_set_error prefix=%s", key_prefix)

    async def get_version(self, namespace: str) -> int:
        if self._client is None: return CACHE_NAMESPACE_DEFAULT_VERSION
        key = f"{CACHE_NAMESPACE_KEY_PREFIX}:{namespace}"
        try:
            raw = await self._client.get(key)
            if raw is None:
                await self._client.set(key, CACHE_NAMESPACE_DEFAULT_VERSION)
                return CACHE_NAMESPACE_DEFAULT_VERSION

            version = int(raw)
            if version < 1:
                await self._client.set(key, CACHE_NAMESPACE_DEFAULT_VERSION)
                return CACHE_NAMESPACE_DEFAULT_VERSION

            return version
        except Exception:
            logger.exception("cache_namespace_get_error namespace=%s", namespace)
            return CACHE_NAMESPACE_DEFAULT_VERSION

    async def bump_namespace(self, namespace: str) -> int:
        if self._client is None: return CACHE_NAMESPACE_DEFAULT_VERSION
        key = f"{CACHE_NAMESPACE_KEY_PREFIX}:{namespace}"
        try:
            version = int(await self._client.incr(key))
            logger.info("cache_namespace_bump namespace=%s version=%s", namespace, version)
            return version

        except Exception:
            logger.exception("cache_namespace_bump_error namespace=%s", namespace)
            return CACHE_NAMESPACE_DEFAULT_VERSION

    async def versioned_key(self, namespace: str, base_key: str) -> str:
        version = await self.get_version(namespace)
        return f"{namespace}:v{version}:{base_key}"
