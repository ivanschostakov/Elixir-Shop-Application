from fastapi.testclient import TestClient


def test_delete_account_deactivates_user_and_revokes_session(client: TestClient, register_verified_user):
    payload = {
        "username": "delete_me_user",
        "email": "delete-me@example.com",
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
        "/api/v1/auth/login",
        json={"login": payload["email"], "password": payload["password"], "is_email": True},
    )
    assert login_response.status_code == 401, login_response.text

