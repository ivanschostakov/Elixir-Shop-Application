from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

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
from src.database import get_db
from src.database.models import Admin, AdminAuditLog, AdminRole, AdminRoleAssignment, AdminSavedView, User

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
    rows = list((await db.execute(select(AdminRole).where(AdminRole.code.in_(normalized)))).scalars().all())
    if len(rows) != len(normalized):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more roles do not exist")
    return rows


@admin_settings_router.get("/roles", response_model=list[AdminRoleRead])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("staff.manage")),
) -> list[AdminRoleRead]:
    rows = list((await db.execute(select(AdminRole).order_by(AdminRole.id))).scalars().all())
    return [AdminRoleRead.model_validate(row) for row in rows]


@admin_settings_router.get("/staff", response_model=list[StaffRead])
async def list_staff(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("staff.manage")),
) -> list[StaffRead]:
    rows = list((await db.execute(select(Admin).options(
        joinedload(Admin.user),
        selectinload(Admin.role_assignments).selectinload(AdminRoleAssignment.role),
    ).order_by(Admin.user_id))).scalars().unique().all())
    return [_staff_read(row) for row in rows]


@admin_settings_router.post("/staff", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
async def create_staff(
    payload: StaffCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> StaffRead:
    user = (await db.execute(select(User).where(User.email == str(payload.email).lower()))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A registered user with this email is required")
    if await db.get(Admin, user.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already an administrator")
    roles = await _resolve_roles(db, payload.role_codes)
    admin = Admin(user_id=user.id, is_active=True)
    db.add(admin)
    await db.flush()
    for role in roles:
        db.add(AdminRoleAssignment(admin_user_id=user.id, role_id=role.id, assigned_by_user_id=context.user.id))
    await db.flush()
    admin = await get_admin_by_user_id(db, user.id)
    result = _staff_read(admin)
    await add_admin_audit(db, request, context, action="staff.create", entity_type="admin", entity_id=user.id, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_settings_router.put("/staff/{user_id}/roles", response_model=StaffRead)
async def update_staff_roles(
    user_id: int,
    payload: StaffRolesPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> StaffRead:
    admin = await get_admin_by_user_id(db, user_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found")
    roles = await _resolve_roles(db, payload.role_codes)
    if user_id == context.user.id and "superadmin" not in {role.code for role in roles} and "superadmin" in context.roles:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot remove your own superadmin role")
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
    admin = await get_admin_by_user_id(db, user_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found")
    if user_id == context.user.id and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot disable your own account")
    before = _staff_read(admin).model_dump(mode="json")
    admin.is_active = payload.is_active
    await db.flush()
    result = _staff_read(admin)
    await add_admin_audit(db, request, context, action="staff.status.update", entity_type="admin", entity_id=user_id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


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
