from collections.abc import Iterable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app.services.cache import get_cache_service


class FakeRedisForSearches:
    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.expirations: dict[str, int] = {}

    async def zrevrange(self, key: str, start: int, stop: int):
        items = sorted((self.zsets.get(key) or {}).items(), key=lambda item: item[1], reverse=True)
        if stop < 0:
            return []
        return [value for value, _score in items[start: stop + 1]]

    async def zadd(self, key: str, mapping: dict[str, float]):
        bucket = self.zsets.setdefault(key, {})
        for member, score in mapping.items():
            bucket[member] = float(score)
        return len(mapping)

    async def zcard(self, key: str):
        return len(self.zsets.get(key, {}))

    async def zremrangebyrank(self, key: str, start: int, stop: int):
        bucket = self.zsets.get(key, {})
        if not bucket:
            return 0
        sorted_items = sorted(bucket.items(), key=lambda item: item[1])
        removable = sorted_items[start: stop + 1]
        for member, _score in removable:
            bucket.pop(member, None)
        return len(removable)

    async def expire(self, key: str, seconds: int):
        self.expirations[key] = seconds
        return True

    async def delete(self, key: str):
        existed = key in self.zsets
        self.zsets.pop(key, None)
        self.expirations.pop(key, None)
        return 1 if existed else 0


def _auth_headers(payload: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {payload['access_token']}"}


@pytest.fixture()
def redis_search_cache(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedisForSearches()
    cache = get_cache_service()
    previous_client = cache.client
    cache._client = fake  # type: ignore[assignment]
    try:
        yield fake
    finally:
        cache._client = previous_client  # type: ignore[assignment]


def test_recent_search_queries_requires_authentication(client: TestClient):
    response = client.get("/api/v1/users/me/search-queries")
    assert response.status_code == 401, response.text


def test_recent_search_queries_add_list_dedupe_and_clear(
    client: TestClient,
    register_verified_user,
    redis_search_cache: FakeRedisForSearches,
):
    auth = register_verified_user(
        {
            "username": f"rsu{uuid4().hex[:8]}",
            "email": f"recent-search-user-{uuid4().hex[:8]}@example.com",
            "password": "test-password",
            "name": "Recent",
            "surname": "Search",
        }
    )
    headers = _auth_headers(auth)

    add_first = client.post("/api/v1/users/me/search-queries", headers=headers, json={"query": " Peptide "})
    assert add_first.status_code == 204, add_first.text

    add_second = client.post("/api/v1/users/me/search-queries", headers=headers, json={"query": "peptide"})
    assert add_second.status_code == 204, add_second.text

    listed = client.get("/api/v1/users/me/search-queries", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == ["peptide"]

    cleared = client.delete("/api/v1/users/me/search-queries", headers=headers)
    assert cleared.status_code == 204, cleared.text

    listed_after_clear = client.get("/api/v1/users/me/search-queries", headers=headers)
    assert listed_after_clear.status_code == 200, listed_after_clear.text
    assert listed_after_clear.json() == []


def test_recent_search_queries_trim_to_twenty(
    client: TestClient,
    register_verified_user,
    redis_search_cache: FakeRedisForSearches,
):
    auth = register_verified_user(
        {
            "username": f"rsu{uuid4().hex[:8]}",
            "email": f"recent-search-user-{uuid4().hex[:8]}@example.com",
            "password": "test-password",
            "name": "Recent2",
            "surname": "Search2",
        }
    )
    headers = _auth_headers(auth)

    def add_many(values: Iterable[str]):
        for value in values:
            response = client.post("/api/v1/users/me/search-queries", headers=headers, json={"query": value})
            assert response.status_code == 204, response.text

    values = [f"query-{index}" for index in range(25)]
    add_many(values)

    listed = client.get("/api/v1/users/me/search-queries", headers=headers, params={"limit": 20})
    assert listed.status_code == 200, listed.text

    payload = listed.json()
    assert len(payload) == 20
    assert payload[0] == "query-24"
    assert payload[-1] == "query-5"
