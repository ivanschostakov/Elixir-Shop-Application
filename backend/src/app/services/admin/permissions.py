from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import ADMIN_READ_ONLY, ufa_now
from src.app.services.admin.security import decode_admin_token
from src.database import get_db
from src.database.models import Admin, AdminRoleAssignment, User, UserSession

admin_bearer_scheme = HTTPBearer(auto_error=False)

ALL_PERMISSIONS: tuple[str, ...] = (
    "dashboard.read",
    "orders.read",
    "orders.transition",
    "orders.recover",
    "customers.read",
    "customers.manage",
    "customers.delete",
    "customers.notes",
    "tasks.read",
    "tasks.manage",
    "segments.read",
    "segments.manage",
    "campaigns.read",
    "campaigns.manage",
    "campaigns.send",
    "automation.read",
    "automation.manage",
    "sla.read",
    "sla.manage",
    "alerts.read",
    "alerts.manage",
    "catalog.read",
    "catalog.merchandise",
    "categories.manage",
    "reviews.read",
    "reviews.moderate",
    "banners.manage",
    "referrals.read",
    "notifications.manage",
    "community.read",
    "ai_chats.read",
    "support.read",
    "support.reply",
    "support.assign",
    "leads.read",
    "leads.manage",
    "analytics.read",
    "integrations.read",
    "integrations.retry",
    "staff.manage",
    "audit.read",
    "exports.read",
)


@dataclass(frozen=True, slots=True)
class AdminContext:
    user: User
    admin: Admin
    session: UserSession
    roles: tuple[str, ...]
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions


def _unauthorized(detail: str = "Could not validate admin credentials") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def get_admin_by_user_id(db: AsyncSession, user_id: int) -> Admin | None:
    stmt = (
        select(Admin)
        .options(
            joinedload(Admin.user),
            selectinload(Admin.role_assignments).selectinload(AdminRoleAssignment.role),
        )
        .where(Admin.user_id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def build_admin_context(*, admin: Admin, session: UserSession) -> AdminContext:
    roles = tuple(sorted({assignment.role.code for assignment in admin.role_assignments}))
    permissions = frozenset(
        permission
        for assignment in admin.role_assignments
        for permission in (assignment.role.permissions or [])
    )
    return AdminContext(user=admin.user, admin=admin, session=session, roles=roles, permissions=permissions)


async def get_current_admin_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    payload = decode_admin_token(credentials.credentials, expected_type="admin_access")
    if payload is None:
        raise _unauthorized()
    try:
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    session = await db.get(UserSession, session_id)
    if (
        session is None
        or session.user_id != user_id
        or session.purpose != "admin"
        or session.mfa_verified_at is None
        or session.revoked_at is not None
        or session.expires_at <= ufa_now()
    ):
        raise _unauthorized()
    admin = await get_admin_by_user_id(db, user_id)
    if admin is None or not admin.is_active or not admin.user.is_active or admin.mfa_confirmed_at is None:
        raise _unauthorized()
    return build_admin_context(admin=admin, session=session)


def require_permission(permission: str, *, write: bool = False):
    async def dependency(context: AdminContext = Depends(get_current_admin_context)) -> AdminContext:
        if not context.has_permission(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission}")
        if write and ADMIN_READ_ONLY:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin panel is in read-only mode")
        return context

    return dependency
