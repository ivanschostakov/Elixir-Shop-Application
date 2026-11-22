import uuid

import pytest
from fastapi.testclient import TestClient


def test_delete_account_removes_user_and_revokes_session(client: TestClient, register_verified_user, monkeypatch: pytest.MonkeyPatch, tmp_path):
    token = uuid.uuid4().hex[:10]
    payload = {
        "email": f"delete-me-{token}@example.com",
        "password": "StrongPass123!",
        "name": "Delete",
        "surname": "Me",
    }
    auth = register_verified_user(payload)
    access_token = auth["access_token"]
    import config
    from src.app.services import avatar_storage
    monkeypatch.setattr(config, "AVATARS_MEDIA_DIR", tmp_path)
    monkeypatch.setattr(avatar_storage, "AVATARS_MEDIA_DIR", tmp_path)
    avatars = [tmp_path / f"{auth['user']['id']}{ext}" for ext in (".png", ".jpeg")]
    for path in avatars: path.write_bytes(b"avatar")
    unrelated = tmp_path / "unrelated.png"
    unrelated.write_bytes(b"keep")

    delete_response = client.delete(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["ok"] is True
    assert all(not path.exists() for path in avatars)
    assert unrelated.read_bytes() == b"keep"

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 401, me_response.text

    login_response = client.post(
        "/api/v1/auth/login",
        json={"login": payload["email"], "password": payload["password"]},
    )
    assert login_response.status_code == 401, login_response.text
