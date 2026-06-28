import uuid

import pytest
from fastapi.testclient import TestClient


def test_delete_account_deactivates_user_and_revokes_session(client: TestClient, register_verified_user, monkeypatch: pytest.MonkeyPatch):
    token = uuid.uuid4().hex[:10]
    payload = {
        "username": f"del{token}",
        "email": f"delete-me-{token}@example.com",
        "phone_number": "+79990000000",
        "password": "StrongPass123!",
        "name": "Delete",
        "surname": "Me",
    }
    auth = register_verified_user(payload)
    access_token = auth["access_token"]

    delete_response = client.delete(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["ok"] is True

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 401, me_response.text

    login_response = client.post(
        "/api/v1/auth/phone/login",
        json={"phone_number": payload["phone_number"], "password": payload["password"]},
    )
    assert login_response.status_code == 401, login_response.text
