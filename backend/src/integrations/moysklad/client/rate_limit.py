"""Pace requests for one accounting credential across API and worker processes."""
import asyncio
import hashlib
import logging
from math import ceil
from time import monotonic

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .utils import moysklad_retry_after_seconds

logger = logging.getLogger(__name__)

# Positive: provider cooldown. Negative: normal spacing before the next slot.
_SLOT = """
local cooldown = redis.call('pttl', KEYS[1])
if cooldown > 0 then return cooldown end
if redis.call('set', KEYS[2], '1', 'px', ARGV[1], 'nx') then return 0 end
return -math.max(1, redis.call('pttl', KEYS[2]))
"""
_EXTEND = """
if redis.call('pttl', KEYS[1]) < tonumber(ARGV[1]) then
    redis.call('set', KEYS[1], '1', 'px', ARGV[1])
end
return 0
"""


class MoySkladRateLimited(httpx.HTTPStatusError):
    pass


class PacedMoySkladClient(httpx.AsyncClient):
    interval = 0.15
    short_retry = 3

    def __init__(self, *, credential, redis_url=None, **kwargs):
        super().__init__(**kwargs)
        digest = hashlib.sha256(credential.encode()).hexdigest()[:24]
        self._key = f"moysklad:rate:{{{digest}}}"
        self._redis = Redis.from_url(redis_url, socket_connect_timeout=0.25, socket_timeout=0.25) if redis_url else None
        self._redis_retry_at = self._cooldown = self._next_slot = 0.
        self._slots = asyncio.Semaphore(2)

    async def _shared(self, script, keys, value):
        if self._redis is None or monotonic() < self._redis_retry_at:
            return 0
        try:
            async with asyncio.timeout(0.4):
                return int(await self._redis.eval(script, len(keys), *keys, value))
        except (RedisError, OSError, TimeoutError):
            self._redis_retry_at = monotonic() + 5
            logger.warning("MoySklad shared limiter unavailable; applying local pacing")
            return 0

    @staticmethod
    def _defer(request, delay):
        response = httpx.Response(429, headers={"Retry-After": str(max(1, ceil(delay)))}, request=request)
        raise MoySkladRateLimited("MoySklad request deferred", request=request, response=response)

    async def _acquire_slot(self, request):
        deadline = monotonic() + self.short_retry
        while True:
            now = monotonic()
            if self._cooldown > now:
                self._defer(request, self._cooldown - now)
            if now >= deadline:
                self._defer(request, 1)
            if self._next_slot > now:
                await asyncio.sleep(self._next_slot - now)
                continue
            self._next_slot = now + self.interval
            delay_ms = await self._shared(_SLOT, [self._key + ":pause", self._key + ":slot"], ceil(self.interval * 1000))
            if delay_ms > 0:
                self._cooldown = max(self._cooldown, monotonic() + delay_ms / 1000)
                self._defer(request, delay_ms / 1000)
            if delay_ms == 0:
                return
            await asyncio.sleep(-delay_ms / 1000)

    async def send(self, request, **kwargs):
        for attempt in range(2):
            async with self._slots:
                await self._acquire_slot(request)
                response = await super().send(request, **kwargs)
                if response.status_code != 429:
                    return response
                await response.aclose()
                delay = moysklad_retry_after_seconds(response, default=0.5)
                self._cooldown = max(self._cooldown, monotonic() + delay)
                await self._shared(_EXTEND, [self._key + ":pause"], ceil(delay * 1000))
            if attempt or request.method not in {"GET", "HEAD"} or delay > self.short_retry:
                raise MoySkladRateLimited("MoySklad rate limit", request=request, response=response)
            await asyncio.sleep(delay)

    async def aclose(self):
        try:
            await super().aclose()
        finally:
            if self._redis is not None:
                await self._redis.aclose()
