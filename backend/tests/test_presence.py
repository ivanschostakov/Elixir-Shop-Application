from types import SimpleNamespace

import pytest

from src.app.main import app
from src.app.modules.users.me.presence import heartbeat_my_presence


def test_presence_heartbeat_route_is_registered():
    assert "/api/v1/users/me/presence/heartbeat" in app.openapi()["paths"]


@pytest.mark.anyio
async def test_presence_heartbeat_updates_last_active_at():
    user = SimpleNamespace(last_active_at=None)

    class FakeDb:
        committed = False

        async def commit(self):
            self.committed = True

    db = FakeDb()
    response = await heartbeat_my_presence(db=db, current_user=user)

    assert response.ok is True
    assert response.seen_at == user.last_active_at
    assert db.committed is True
