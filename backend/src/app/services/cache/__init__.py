from .client import CacheService
from .constants import CACHE_NAMESPACE_DEFAULT_VERSION
from .helpers import jitter_ttl_seconds, build_cache_key

cache_service = CacheService()

def get_cache_service() -> CacheService: return cache_service

__all__ = [
    "CACHE_NAMESPACE_DEFAULT_VERSION",
    "CacheService",
    "build_cache_key",
    "cache_service",
    "get_cache_service",
    "jitter_ttl_seconds",
]