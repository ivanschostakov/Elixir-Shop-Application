from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.scripts import publish_welcome_banner as publisher


@pytest.mark.anyio
@pytest.mark.parametrize("connected", [True, False])
async def test_publisher_connects_before_invalidating_banner_cache(monkeypatch, tmp_path, connected):
    events = []
    banner = SimpleNamespace(id=4)

    class Database:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def scalar(self, statement):
            return banner

        async def commit(self):
            events.append("commit")

    class Cache:
        client = None

        async def connect(self):
            events.append("connect")
            if connected:
                self.client = object()

        async def bump_namespace(self, namespace):
            assert self.client is not None and namespace == "banners"
            events.append("bump")

        async def close(self):
            events.append("close")

    monkeypatch.setattr(publisher, "SessionLocal", Database)
    monkeypatch.setattr(publisher, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(publisher, "get_cache_service", Cache)
    monkeypatch.setattr(publisher, "engine", SimpleNamespace(dispose=AsyncMock()))
    if connected:
        await publisher.main()
        assert events == ["commit", "connect", "bump", "close"]
        assert banner.id == 4 and banner.image_path.endswith("v2.jpg")
        assert (tmp_path / "banners/welcome-elixirpeptide-v2.jpg").is_file()
    else:
        with pytest.raises(RuntimeError, match="Redis cache invalidation is unavailable"):
            await publisher.main()
        assert events == ["commit", "connect", "close"]
