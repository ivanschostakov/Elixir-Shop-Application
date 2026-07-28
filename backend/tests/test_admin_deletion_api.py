import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.app.main import app
from src.app.services.admin.permissions import AdminContext, get_current_admin_context
from src.database.models import (
    Admin,
    AdminIdentity,
    AdminRole,
    AdminRoleAssignment,
    User,
    UserSession,
)


SYNC_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _create_admin_identity(*, customer_user_id: int, role_code: str) -> int:
    with Session(sync_engine) as session:
        customer = session.get(User, customer_user_id)
        assert customer is not None
        identity = AdminIdentity(
            email=customer.email,
            password_hash=customer.password_hash,
            name=customer.name,
            surname=customer.surname,
            is_active=True,
        )
        session.add(identity)
        session.flush()
        admin = Admin(
            user_id=identity.id,
            is_active=True,
            mfa_confirmed_at=datetime.now(timezone.utc),
        )
        session.add(admin)
        admin.mfa_confirmed_at = datetime.now(timezone.utc)
        role = session.execute(select(AdminRole).where(AdminRole.code == role_code)).scalar_one()
        session.add(
            AdminRoleAssignment(
                admin_user_id=identity.id,
                role_id=role.id,
                assigned_by_user_id=identity.id,
            )
        )
        session.commit()
        return int(identity.id)


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)
            session.commit()


def _delete_admin_identity(admin_user_id: int) -> None:
    with Session(sync_engine) as session:
        identity = session.get(AdminIdentity, admin_user_id)
        if identity is not None:
            session.delete(identity)
            session.commit()


def _admin_context(user_id: int, *, name: str = "Super", surname: str = "Admin") -> AdminContext:
    return AdminContext(
        user=SimpleNamespace(id=user_id, name=name, surname=surname),
        admin=SimpleNamespace(user_id=user_id),
        session=SimpleNamespace(id=1),
        roles=("superadmin",),
        permissions=frozenset({"*"}),
    )


def test_admin_can_permanently_delete_customer_profile(
    client: TestClient,
    register_verified_user,
):
    operator = register_verified_user({
        "email": f"delete-operator-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Super",
        "surname": "Admin",
    })
    customer = register_verified_user({
        "email": f"delete-customer-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Delete",
        "surname": "Customer",
    })
    operator_customer_id = int(operator["user"]["id"])
    customer_id = int(customer["user"]["id"])
    operator_admin_id = _create_admin_identity(
        customer_user_id=operator_customer_id,
        role_code="superadmin",
    )
    app.dependency_overrides[get_current_admin_context] = lambda: _admin_context(operator_admin_id)

    try:
        detail = client.get(f"/api/v1/admin/customers/{customer_id}")
        assert detail.status_code == 200, detail.text

        invalid = client.request(
            "DELETE",
            f"/api/v1/admin/customers/{customer_id}",
            json={"confirmation": "delete", "expected_updated_at": detail.json()["updated_at"]},
        )
        assert invalid.status_code == 422, invalid.text

        deleted = client.request(
            "DELETE",
            f"/api/v1/admin/customers/{customer_id}",
            json={"confirmation": "DELETE", "expected_updated_at": detail.json()["updated_at"]},
        )
        assert deleted.status_code == 204, deleted.text

        with Session(sync_engine) as session:
            assert session.get(User, customer_id) is None
            sessions_count = session.scalar(
                select(func.count(UserSession.id)).where(UserSession.user_id == customer_id)
            )
            assert sessions_count == 0
    finally:
        app.dependency_overrides.pop(get_current_admin_context, None)
        _delete_user(customer_id)
        _delete_admin_identity(operator_admin_id)
        _delete_user(operator_customer_id)


def test_admin_can_remove_staff_access_without_deleting_customer(
    client: TestClient,
    register_verified_user,
):
    operator = register_verified_user({
        "email": f"remove-operator-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Super",
        "surname": "Admin",
    })
    employee = register_verified_user({
        "email": f"remove-employee-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Support",
        "surname": "Agent",
    })
    operator_customer_id = int(operator["user"]["id"])
    employee_customer_id = int(employee["user"]["id"])
    operator_admin_id = _create_admin_identity(
        customer_user_id=operator_customer_id,
        role_code="superadmin",
    )
    employee_admin_id = _create_admin_identity(
        customer_user_id=employee_customer_id,
        role_code="support",
    )
    app.dependency_overrides[get_current_admin_context] = lambda: _admin_context(operator_admin_id)

    try:
        removed = client.delete(f"/api/v1/admin/staff/{employee_admin_id}")
        assert removed.status_code == 204, removed.text

        staff = client.get("/api/v1/admin/staff")
        assert staff.status_code == 200, staff.text
        assert employee_admin_id not in {row["user_id"] for row in staff.json()}

        with Session(sync_engine) as session:
            admin = session.get(Admin, employee_admin_id)
            assert admin is not None
            assert admin.is_active is False
            assert admin.mfa_confirmed_at is None
            assignments_count = session.scalar(
                select(func.count())
                .select_from(AdminRoleAssignment)
                .where(AdminRoleAssignment.admin_user_id == employee_admin_id)
            )
            assert assignments_count == 0
            assert session.get(AdminIdentity, employee_admin_id) is not None
            assert session.get(User, employee_customer_id) is not None

        cannot_remove_self = client.delete(f"/api/v1/admin/staff/{operator_admin_id}")
        assert cannot_remove_self.status_code == 409, cannot_remove_self.text
    finally:
        app.dependency_overrides.pop(get_current_admin_context, None)
        _delete_admin_identity(employee_admin_id)
        _delete_admin_identity(operator_admin_id)
        _delete_user(employee_customer_id)
        _delete_user(operator_customer_id)


def test_invitation_creates_credentials_independent_from_customer_account(
    client: TestClient,
    register_verified_user,
    monkeypatch: pytest.MonkeyPatch,
):
    operator = register_verified_user({
        "email": f"invite-operator-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Super",
        "surname": "Admin",
    })
    shared_email = f"separate-identity-{uuid.uuid4().hex[:10]}@example.com"
    customer = register_verified_user({
        "email": shared_email,
        "password": "CustomerPassword123!",
        "name": "Buyer",
        "surname": "Profile",
    })
    operator_customer_id = int(operator["user"]["id"])
    customer_id = int(customer["user"]["id"])
    operator_admin_id = _create_admin_identity(
        customer_user_id=operator_customer_id,
        role_code="superadmin",
    )
    token_box: dict[str, str] = {}

    async def capture_invitation(**kwargs) -> None:
        token_box["token"] = str(kwargs["token"])

    monkeypatch.setattr(
        "src.app.modules.admin.invitations.send_admin_invitation_email",
        capture_invitation,
    )
    app.dependency_overrides[get_current_admin_context] = lambda: _admin_context(operator_admin_id)

    invited_admin_id: int | None = None
    try:
        invitation = client.post(
            "/api/v1/admin/staff/invitations",
            json={"email": shared_email, "role_codes": ["support"]},
        )
        assert invitation.status_code == 201, invitation.text
        token = token_box["token"]

        preview = client.post(
            "/api/v1/admin/auth/invitations/preview",
            json={"token": token},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["existing_user"] is False

        accepted = client.post(
            "/api/v1/admin/auth/invitations/accept",
            json={
                "token": token,
                "name": "Support",
                "surname": "Agent",
                "password": "IndependentAdminPassword123!",
            },
        )
        assert accepted.status_code == 200, accepted.text

        with Session(sync_engine) as session:
            customer_row = session.get(User, customer_id)
            identity = session.execute(
                select(AdminIdentity).where(AdminIdentity.email == shared_email)
            ).scalar_one()
            invited_admin_id = int(identity.id)
            assert customer_row is not None
            assert identity.id != customer_row.id
            assert session.get(Admin, identity.id) is not None

        customer_login = client.post(
            "/api/v1/auth/login",
            json={"login": shared_email, "password": "CustomerPassword123!"},
        )
        assert customer_login.status_code == 200, customer_login.text

        wrong_admin_password = client.post(
            "/api/v1/admin/auth/login",
            json={"email": shared_email, "password": "CustomerPassword123!"},
        )
        assert wrong_admin_password.status_code == 401, wrong_admin_password.text

        admin_login = client.post(
            "/api/v1/admin/auth/login",
            json={
                "email": shared_email,
                "password": "IndependentAdminPassword123!",
            },
        )
        assert admin_login.status_code == 200, admin_login.text
        assert admin_login.json()["status"] == "mfa_setup_required"
    finally:
        app.dependency_overrides.pop(get_current_admin_context, None)
        if invited_admin_id is not None:
            _delete_admin_identity(invited_admin_id)
        _delete_admin_identity(operator_admin_id)
        _delete_user(customer_id)
        _delete_user(operator_customer_id)
