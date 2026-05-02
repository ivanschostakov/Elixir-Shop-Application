import asyncio

from src.app.services.cache import CacheService, build_cache_key, jitter_ttl_seconds


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ex: int | None = None):
        self.store[key] = str(value)
        return True

    async def incr(self, key: str):
        current = int(self.store.get(key) or 0) + 1
        self.store[key] = str(current)
        return current


def test_build_cache_key_is_stable_and_sorted():
    key1 = build_cache_key(route="products:list", params={"q": " test ", "limit": 20, "offset": 0})
    key2 = build_cache_key(route="products:list", params={"offset": 0, "q": "test", "limit": 20})
    assert key1 == key2


def test_jitter_ttl_is_within_expected_bounds():
    ttl = 100
    for _ in range(100):
        jittered = jitter_ttl_seconds(ttl)
        assert 80 <= jittered <= 120


def test_namespace_version_defaults_and_bumps():
    async def scenario():
        service = CacheService(redis_url="redis://fake")
        service._client = FakeRedis()  # type: ignore[assignment]

        version = await service.get_version("catalog")
        assert version == 1

        version = await service.bump_namespace("catalog")
        assert version == 2

        key = await service.versioned_key("catalog", "products:list:{}")
        assert key.startswith("catalog:v2:")

    asyncio.run(scenario())
