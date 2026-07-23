import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.app.main import app
from src.app.services.admin.permissions import AdminContext, get_current_admin_context
from src.database.models import Admin, AdminRole, AdminRoleAssignment, User, UserSession


SYNC_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
sync_engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)


def _promote(*, user_id: int, role_code: str) -> None:
    with Session(sync_engine) as session:
        admin = session.get(Admin, user_id)
        if admin is None:
            admin = Admin(user_id=user_id, is_active=True)
            session.add(admin)
        admin.is_active = True
        admin.mfa_confirmed_at = datetime.now(timezone.utc)
        role = session.execute(select(AdminRole).where(AdminRole.code == role_code)).scalar_one()
        session.merge(AdminRoleAssignment(admin_user_id=user_id, role_id=role.id, assigned_by_user_id=user_id))
        session.commit()


def _delete_user(user_id: int) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)
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
    operator_id = int(operator["user"]["id"])
    customer_id = int(customer["user"]["id"])
    _promote(user_id=operator_id, role_code="superadmin")
    app.dependency_overrides[get_current_admin_context] = lambda: _admin_context(operator_id)

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
        _delete_user(operator_id)


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
    operator_id = int(operator["user"]["id"])
    employee_id = int(employee["user"]["id"])
    _promote(user_id=operator_id, role_code="superadmin")
    _promote(user_id=employee_id, role_code="support")
    app.dependency_overrides[get_current_admin_context] = lambda: _admin_context(operator_id)

    try:
        removed = client.delete(f"/api/v1/admin/staff/{employee_id}")
        assert removed.status_code == 204, removed.text

        staff = client.get("/api/v1/admin/staff")
        assert staff.status_code == 200, staff.text
        assert employee_id not in {row["user_id"] for row in staff.json()}

        with Session(sync_engine) as session:
            admin = session.get(Admin, employee_id)
            assert admin is not None
            assert admin.is_active is False
            assert admin.mfa_confirmed_at is None
            assignments_count = session.scalar(
                select(func.count())
                .select_from(AdminRoleAssignment)
                .where(AdminRoleAssignment.admin_user_id == employee_id)
            )
            assert assignments_count == 0
            assert session.get(User, employee_id) is not None

        cannot_remove_self = client.delete(f"/api/v1/admin/staff/{operator_id}")
        assert cannot_remove_self.status_code == 409, cannot_remove_self.text
    finally:
        app.dependency_overrides.pop(get_current_admin_context, None)
        _delete_user(employee_id)
        _delete_user(operator_id)
