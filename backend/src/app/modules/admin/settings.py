from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import ufa_now
from src.app.modules.admin.schemas import (
    AdminPage,
    AdminRoleRead,
    AuditLogRead,
    SavedViewPayload,
    SavedViewRead,
    StaffCreatePayload,
    StaffRead,
    StaffRolesPayload,
    StaffStatusPayload,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.admin.permissions import get_admin_by_user_id
from src.app.services.admin.role_catalog import ASSIGNABLE_ROLE_CODES, SYSTEM_ROLE_BY_CODE
from src.database import get_db
from src.database.models import (
    Admin,
    AdminAuditLog,
    AdminRole,
    AdminRoleAssignment,
    AdminSavedView,
    User,
    UserSession,
)

admin_settings_router = APIRouter(tags=["admin_settings"])


def _staff_read(admin: Admin) -> StaffRead:
    return StaffRead(
        user_id=admin.user_id,
        email=admin.user.email,
        name=admin.user.name,
        surname=admin.user.surname,
        is_active=admin.is_active,
        mfa_enabled=admin.mfa_confirmed_at is not None,
        last_login_at=admin.last_login_at,
        role_codes=sorted(assignment.role.code for assignment in admin.role_assignments),
    )


async def _resolve_roles(db: AsyncSession, role_codes: list[str]) -> list[AdminRole]:
    normalized = sorted(set(role_codes))
    unknown = sorted(set(normalized) - ASSIGNABLE_ROLE_CODES)
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown roles: {', '.join(unknown)}")
    if "superadmin" in normalized and len(normalized) > 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The super administrator role must be assigned on its own")
    rows = list((await db.execute(select(AdminRole).where(AdminRole.code.in_(normalized)))).scalars().all())
    if len(rows) != len(normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more roles do not exist")
    return rows


def _role_codes(admin: Admin) -> set[str]:
    return {assignment.role.code for assignment in admin.role_assignments}


def _ensure_staff_exists(admin: Admin | None) -> Admin:
    if admin is None or not admin.role_assignments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found")
    return admin


async def _ensure_not_last_active_superadmin(db: AsyncSession, admin: Admin) -> None:
    if not admin.is_active or not admin.user.is_active or "superadmin" not in _role_codes(admin):
        return
    active_superadmin_ids = list((await db.execute(
        select(Admin.user_id)
        .join(User, User.id == Admin.user_id)
        .join(AdminRoleAssignment, AdminRoleAssignment.admin_user_id == Admin.user_id)
        .join(AdminRole, AdminRole.id == AdminRoleAssignment.role_id)
        .where(
            Admin.is_active.is_(True),
            User.is_active.is_(True),
            AdminRole.code == "superadmin",
        )
        .order_by(Admin.user_id)
        .with_for_update(of=Admin)
    )).scalars().all())
    if len(active_superadmin_ids) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active super administrator cannot be removed or disabled",
        )


@admin_settings_router.get("/roles", response_model=list[AdminRoleRead])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("staff.manage")),
) -> list[AdminRoleRead]:
    rows = list((await db.execute(select(AdminRole).order_by(AdminRole.id))).scalars().all())
    return [
        AdminRoleRead(
            id=row.id,
            code=row.code,
            name_ru=row.name_ru,
            name_en=row.name_en,
            permissions=row.permissions,
            description_ru=SYSTEM_ROLE_BY_CODE.get(row.code).description_ru if row.code in SYSTEM_ROLE_BY_CODE else "",
            description_en=SYSTEM_ROLE_BY_CODE.get(row.code).description_en if row.code in SYSTEM_ROLE_BY_CODE else "",
        )
        for row in rows
    ]


@admin_settings_router.get("/staff", response_model=list[StaffRead])
async def list_staff(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("staff.manage")),
) -> list[StaffRead]:
    rows = list((await db.execute(select(Admin).options(
        joinedload(Admin.user),
        selectinload(Admin.role_assignments).selectinload(AdminRoleAssignment.role),
    ).where(Admin.role_assignments.any()).order_by(Admin.user_id))).scalars().unique().all())
    return [_staff_read(row) for row in rows]


@admin_settings_router.post("/staff", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> StaffRead:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Direct staff creation is disabled. Use the email invitation flow.",
    )


@admin_settings_router.put("/staff/{user_id}/roles", response_model=StaffRead)
async def update_staff_roles(
    user_id: int,
    payload: StaffRolesPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> StaffRead:
    admin = _ensure_staff_exists(await get_admin_by_user_id(db, user_id))
    roles = await _resolve_roles(db, payload.role_codes)
    current_role_codes = _role_codes(admin)
    if "superadmin" in {role.code for role in roles} and "superadmin" not in current_role_codes and not payload.confirm_superadmin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit confirmation is required to grant the super administrator role",
        )
    if user_id == context.user.id and "superadmin" not in {role.code for role in roles} and "superadmin" in context.roles:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own superadmin role")
    if "superadmin" in current_role_codes and "superadmin" not in {role.code for role in roles}:
        await _ensure_not_last_active_superadmin(db, admin)
    before = _staff_read(admin).model_dump(mode="json")
    for assignment in list(admin.role_assignments):
        await db.delete(assignment)
    await db.flush()
    for role in roles:
        db.add(AdminRoleAssignment(admin_user_id=user_id, role_id=role.id, assigned_by_user_id=context.user.id))
    await db.flush()
    admin = await get_admin_by_user_id(db, user_id)
    result = _staff_read(admin)
    await add_admin_audit(db, request, context, action="staff.roles.update", entity_type="admin", entity_id=user_id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_settings_router.patch("/staff/{user_id}/status", response_model=StaffRead)
async def update_staff_status(
    user_id: int,
    payload: StaffStatusPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> StaffRead:
    admin = _ensure_staff_exists(await get_admin_by_user_id(db, user_id))
    if user_id == context.user.id and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot disable your own account")
    if not payload.is_active:
        await _ensure_not_last_active_superadmin(db, admin)
    before = _staff_read(admin).model_dump(mode="json")
    admin.is_active = payload.is_active
    await db.flush()
    result = _staff_read(admin)
    await add_admin_audit(db, request, context, action="staff.status.update", entity_type="admin", entity_id=user_id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_settings_router.delete("/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> None:
    admin = _ensure_staff_exists(await get_admin_by_user_id(db, user_id))
    if user_id == context.user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own staff access")
    await _ensure_not_last_active_superadmin(db, admin)

    before = _staff_read(admin).model_dump(mode="json")
    now = ufa_now()
    sessions = list((await db.execute(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.purpose == "admin",
            UserSession.revoked_at.is_(None),
        )
    )).scalars().all())
    for session in sessions:
        session.revoked_at = now
    for assignment in list(admin.role_assignments):
        await db.delete(assignment)
    admin.is_active = False
    admin.totp_secret_encrypted = None
    admin.mfa_confirmed_at = None
    await add_admin_audit(
        db,
        request,
        context,
        action="staff.remove",
        entity_type="admin",
        entity_id=user_id,
        before=before,
        after={"removed": True, "revoked_sessions": len(sessions)},
    )
    await db.commit()


@admin_settings_router.get("/audit", response_model=AdminPage[AuditLogRead])
async def list_audit_logs(
    q: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=80),
    actor_user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("audit.read")),
) -> AdminPage[AuditLogRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(AdminAuditLog.action.ilike(pattern), AdminAuditLog.entity_id.ilike(pattern)))
    if entity_type:
        filters.append(AdminAuditLog.entity_type == entity_type)
    if actor_user_id:
        filters.append(AdminAuditLog.actor_user_id == actor_user_id)
    total = int((await db.execute(select(func.count(AdminAuditLog.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(AdminAuditLog).options(
        selectinload(AdminAuditLog.actor).joinedload(Admin.user),
    ).where(*filters).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[AuditLogRead(
        id=row.id,
        actor_name=(f"{row.actor.user.name} {row.actor.user.surname}".strip() if row.actor else "Система"),
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before_json=row.before_json,
        after_json=row.after_json,
        context_json=row.context_json,
        ip_address=row.ip_address,
        request_id=row.request_id,
        created_at=row.created_at,
    ) for row in rows], total=total, limit=limit, offset=offset)


@admin_settings_router.get("/saved-views", response_model=list[SavedViewRead])
async def list_saved_views(
    resource: str | None = Query(default=None, max_length=80),
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read")),
) -> list[SavedViewRead]:
    filters = [or_(AdminSavedView.owner_user_id == context.user.id, AdminSavedView.is_shared.is_(True))]
    if resource:
        filters.append(AdminSavedView.resource == resource)
    rows = list((await db.execute(select(AdminSavedView).where(*filters).order_by(AdminSavedView.name))).scalars().all())
    return [SavedViewRead.model_validate(row) for row in rows]


@admin_settings_router.post("/saved-views", response_model=SavedViewRead, status_code=status.HTTP_201_CREATED)
async def create_saved_view(
    payload: SavedViewPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read", write=True)),
) -> SavedViewRead:
    name = payload.name.strip()
    duplicate = (await db.execute(select(AdminSavedView.id).where(
        AdminSavedView.owner_user_id == context.user.id,
        AdminSavedView.resource == payload.resource,
        func.lower(AdminSavedView.name) == name.lower(),
    ))).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Saved view name already exists")
    row = AdminSavedView(owner_user_id=context.user.id, **payload.model_dump(exclude={"name"}), name=name)
    db.add(row)
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="saved_view.create",
        entity_type="saved_view",
        entity_id=row.id,
        after={"resource": row.resource, "name": row.name, "is_shared": row.is_shared},
    )
    await db.commit()
    await db.refresh(row)
    return SavedViewRead.model_validate(row)


@admin_settings_router.put("/saved-views/{view_id}", response_model=SavedViewRead)
async def update_saved_view(
    view_id: int,
    payload: SavedViewPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read", write=True)),
) -> SavedViewRead:
    row = await db.get(AdminSavedView, view_id)
    if row is None or row.owner_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    name = payload.name.strip()
    duplicate = (await db.execute(select(AdminSavedView.id).where(
        AdminSavedView.owner_user_id == context.user.id,
        AdminSavedView.resource == payload.resource,
        func.lower(AdminSavedView.name) == name.lower(),
        AdminSavedView.id != view_id,
    ))).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Saved view name already exists")
    before = {"resource": row.resource, "name": row.name, "state_json": row.state_json, "is_shared": row.is_shared}
    row.resource = payload.resource
    row.name = name
    row.state_json = payload.state_json
    row.is_shared = payload.is_shared
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="saved_view.update",
        entity_type="saved_view",
        entity_id=row.id,
        before=before,
        after={"resource": row.resource, "name": row.name, "state_json": row.state_json, "is_shared": row.is_shared},
    )
    await db.commit()
    await db.refresh(row)
    return SavedViewRead.model_validate(row)


@admin_settings_router.delete("/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_view(
    view_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("dashboard.read", write=True)),
) -> None:
    row = await db.get(AdminSavedView, view_id)
    if row is None or row.owner_user_id != context.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    await add_admin_audit(
        db,
        request,
        context,
        action="saved_view.delete",
        entity_type="saved_view",
        entity_id=row.id,
        before={"resource": row.resource, "name": row.name, "is_shared": row.is_shared},
    )
    await db.delete(row)
    await db.commit()
