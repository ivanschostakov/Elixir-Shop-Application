from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.app.modules.admin.schemas import (
    AdminInvitationAcceptPayload,
    AdminInvitationAcceptResponse,
    AdminInvitationCreatePayload,
    AdminInvitationPreview,
    AdminInvitationRead,
    AdminInvitationTokenPayload,
)
from src.app.services.admin import (
    AdminContext,
    AdminInvitationConfigError,
    AdminInvitationDeliveryError,
    add_admin_audit,
    admin_invitation_expiry,
    admin_invitation_role_names,
    admin_invitation_status,
    generate_admin_invitation_token,
    hash_admin_invitation_token,
    require_permission,
    send_admin_invitation_email,
)
from src.app.services.admin.role_catalog import ASSIGNABLE_ROLE_CODES
from src.app.services.rate_limit import client_ip_from_request, enforce_rate_limit
from src.app.services.security import hash_password, verify_password
from src.database import get_db
from src.database.models import (
    Admin,
    AdminAuditLog,
    AdminInvitation,
    AdminRole,
    AdminRoleAssignment,
    User,
)

admin_invitations_router = APIRouter(tags=["admin_invitations"])


def _inviter_display(user: User | None) -> str:
    if user is None:
        return "Система"
    return f"{user.name} {user.surname}".strip() or user.email or f"Admin {user.id}"


async def _inviter_users(db: AsyncSession, invitations: list[AdminInvitation]) -> dict[int, User]:
    user_ids = {row.invited_by_user_id for row in invitations if row.invited_by_user_id is not None}
    if not user_ids:
        return {}
    rows = list((await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all())
    return {row.id: row for row in rows}


def _invitation_read(invitation: AdminInvitation, inviter: User | None) -> AdminInvitationRead:
    return AdminInvitationRead(
        id=invitation.id,
        email=invitation.email,
        role_codes=list(invitation.role_codes),
        role_names_ru=admin_invitation_role_names(invitation.role_codes, "ru"),
        role_names_en=admin_invitation_role_names(invitation.role_codes, "en"),
        invited_by_name=_inviter_display(inviter),
        status=admin_invitation_status(invitation),
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        last_sent_at=invitation.last_sent_at,
        send_count=invitation.send_count,
    )


async def _resolve_roles(db: AsyncSession, role_codes: list[str]) -> list[AdminRole]:
    unknown = sorted(set(role_codes) - ASSIGNABLE_ROLE_CODES)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown roles: {', '.join(unknown)}",
        )
    rows = list((await db.execute(
        select(AdminRole).where(AdminRole.code.in_(role_codes)).order_by(AdminRole.code)
    )).scalars().all())
    if len(rows) != len(role_codes):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Role catalog is not synchronized. Apply the latest database migration.",
        )
    return rows


async def _admin_is_provisioned(db: AsyncSession, admin: Admin | None) -> bool:
    if admin is None:
        return False
    if admin.is_active:
        return True
    assignment = (await db.execute(
        select(AdminRoleAssignment.admin_user_id)
        .where(AdminRoleAssignment.admin_user_id == admin.user_id)
        .limit(1)
    )).scalar_one_or_none()
    return assignment is not None


async def _load_invitation_by_token(
    db: AsyncSession,
    token: str,
    *,
    lock: bool = False,
) -> AdminInvitation:
    statement = select(AdminInvitation).where(
        AdminInvitation.token_hash == hash_admin_invitation_token(token)
    )
    if lock:
        statement = statement.with_for_update()
    invitation = (await db.execute(statement)).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


def _ensure_pending(invitation: AdminInvitation) -> None:
    current_status = admin_invitation_status(invitation)
    if current_status == "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation has already been accepted")
    if current_status == "revoked":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has been revoked")
    if current_status == "expired":
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")


@admin_invitations_router.get("/staff/invitations", response_model=list[AdminInvitationRead])
async def list_admin_invitations(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("staff.manage")),
) -> list[AdminInvitationRead]:
    rows = list((await db.execute(
        select(AdminInvitation).order_by(AdminInvitation.created_at.desc(), AdminInvitation.id.desc()).limit(250)
    )).scalars().all())
    inviters = await _inviter_users(db, rows)
    return [_invitation_read(row, inviters.get(row.invited_by_user_id or 0)) for row in rows]


@admin_invitations_router.post(
    "/staff/invitations",
    response_model=AdminInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_invitation(
    payload: AdminInvitationCreatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> AdminInvitationRead:
    if "superadmin" in payload.role_codes and not payload.confirm_superadmin:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Explicit confirmation is required to invite a super administrator",
        )
    if "superadmin" in payload.role_codes and len(payload.role_codes) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The super administrator role must be assigned on its own",
        )
    await _resolve_roles(db, payload.role_codes)
    email = str(payload.email).strip().lower()
    existing_user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    existing_admin = await db.get(Admin, existing_user.id) if existing_user is not None else None
    if await _admin_is_provisioned(db, existing_admin):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This user is already an administrator")

    now = ufa_now()
    previous = (await db.execute(
        select(AdminInvitation)
        .where(
            AdminInvitation.email == email,
            AdminInvitation.accepted_at.is_(None),
            AdminInvitation.revoked_at.is_(None),
        )
        .with_for_update()
    )).scalar_one_or_none()
    if previous is not None and previous.expires_at > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active invitation already exists")
    if previous is not None:
        previous.revoked_at = now
        await db.flush()

    token = generate_admin_invitation_token()
    invitation = AdminInvitation(
        email=email,
        token_hash=hash_admin_invitation_token(token),
        role_codes=payload.role_codes,
        invited_by_user_id=context.user.id,
        expires_at=admin_invitation_expiry(now),
        last_sent_at=now,
        send_count=1,
    )
    db.add(invitation)
    await db.flush()
    inviter_name = _inviter_display(context.user)
    try:
        await send_admin_invitation_email(
            to_email=email,
            token=token,
            inviter_name=inviter_name,
            role_codes=payload.role_codes,
            expires_at=invitation.expires_at,
        )
    except (AdminInvitationConfigError, AdminInvitationDeliveryError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    result = _invitation_read(invitation, context.user)
    await add_admin_audit(
        db,
        request,
        context,
        action="staff.invitation.create",
        entity_type="admin_invitation",
        entity_id=invitation.id,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    return result


@admin_invitations_router.post(
    "/staff/invitations/{invitation_id}/resend",
    response_model=AdminInvitationRead,
)
async def resend_admin_invitation(
    invitation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> AdminInvitationRead:
    invitation = (await db.execute(
        select(AdminInvitation).where(AdminInvitation.id == invitation_id).with_for_update()
    )).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Accepted invitation cannot be resent")
    if invitation.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Revoked invitation cannot be resent")
    await _resolve_roles(db, invitation.role_codes)

    inviter = (await db.execute(
        select(User).where(User.id == invitation.invited_by_user_id)
    )).scalar_one_or_none() if invitation.invited_by_user_id else None
    before = _invitation_read(invitation, inviter).model_dump(mode="json")
    token = generate_admin_invitation_token()
    now = ufa_now()
    invitation.token_hash = hash_admin_invitation_token(token)
    invitation.expires_at = admin_invitation_expiry(now)
    invitation.last_sent_at = now
    invitation.send_count += 1
    try:
        await send_admin_invitation_email(
            to_email=invitation.email,
            token=token,
            inviter_name=_inviter_display(context.user),
            role_codes=invitation.role_codes,
            expires_at=invitation.expires_at,
        )
    except (AdminInvitationConfigError, AdminInvitationDeliveryError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    result = _invitation_read(invitation, inviter)
    await add_admin_audit(
        db,
        request,
        context,
        action="staff.invitation.resend",
        entity_type="admin_invitation",
        entity_id=invitation.id,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    return result


@admin_invitations_router.post(
    "/staff/invitations/{invitation_id}/revoke",
    response_model=AdminInvitationRead,
)
async def revoke_admin_invitation(
    invitation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("staff.manage", write=True)),
) -> AdminInvitationRead:
    invitation = (await db.execute(
        select(AdminInvitation).where(AdminInvitation.id == invitation_id).with_for_update()
    )).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Accepted invitation cannot be revoked")
    if invitation.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation is already revoked")
    inviter = (await db.execute(
        select(User).where(User.id == invitation.invited_by_user_id)
    )).scalar_one_or_none() if invitation.invited_by_user_id else None
    before = _invitation_read(invitation, inviter).model_dump(mode="json")
    invitation.revoked_at = ufa_now()
    result = _invitation_read(invitation, inviter)
    await add_admin_audit(
        db,
        request,
        context,
        action="staff.invitation.revoke",
        entity_type="admin_invitation",
        entity_id=invitation.id,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    return result


@admin_invitations_router.post(
    "/auth/invitations/preview",
    response_model=AdminInvitationPreview,
)
async def preview_admin_invitation(
    payload: AdminInvitationTokenPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminInvitationPreview:
    await enforce_rate_limit(
        request,
        scope="admin:invitation:preview",
        limit=30,
        window_seconds=60,
        key=client_ip_from_request(request),
    )
    invitation = await _load_invitation_by_token(db, payload.token)
    inviter = (await db.execute(
        select(User).where(User.id == invitation.invited_by_user_id)
    )).scalar_one_or_none() if invitation.invited_by_user_id else None
    existing_user = (await db.execute(
        select(User.id).where(User.email == invitation.email)
    )).scalar_one_or_none() is not None
    return AdminInvitationPreview(
        email=invitation.email,
        role_codes=list(invitation.role_codes),
        role_names_ru=admin_invitation_role_names(invitation.role_codes, "ru"),
        role_names_en=admin_invitation_role_names(invitation.role_codes, "en"),
        invited_by_name=_inviter_display(inviter),
        status=admin_invitation_status(invitation),
        expires_at=invitation.expires_at,
        existing_user=existing_user,
    )


@admin_invitations_router.post(
    "/auth/invitations/accept",
    response_model=AdminInvitationAcceptResponse,
)
async def accept_admin_invitation(
    payload: AdminInvitationAcceptPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminInvitationAcceptResponse:
    await enforce_rate_limit(
        request,
        scope="admin:invitation:accept",
        limit=10,
        window_seconds=60,
        key=client_ip_from_request(request),
    )
    invitation = await _load_invitation_by_token(db, payload.token, lock=True)
    _ensure_pending(invitation)
    roles = await _resolve_roles(db, invitation.role_codes)

    user = (await db.execute(
        select(User).where(User.email == invitation.email).with_for_update()
    )).scalar_one_or_none()
    if user is None:
        name = (payload.name or "").strip()
        surname = (payload.surname or "").strip()
        if not name or not surname:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name and surname are required for a new account",
            )
        user = User(
            email=invitation.email,
            password_hash=hash_password(payload.password),
            name=name,
            surname=surname,
            is_active=True,
            is_verified=True,
            last_active_at=ufa_now(),
        )
        db.add(user)
        await db.flush()
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
        existing_admin = await db.get(Admin, user.id)
        if await _admin_is_provisioned(db, existing_admin):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already an administrator")
        user.is_verified = True

    admin = await db.get(Admin, user.id)
    if admin is None:
        admin = Admin(user_id=user.id, is_active=True)
        db.add(admin)
    else:
        admin.is_active = True
    await db.flush()
    for role in roles:
        db.add(
            AdminRoleAssignment(
                admin_user_id=user.id,
                role_id=role.id,
                assigned_by_user_id=invitation.invited_by_user_id,
            )
        )
    now = ufa_now()
    invitation.accepted_at = now
    invitation.accepted_by_user_id = user.id
    db.add(
        AdminAuditLog(
            actor_user_id=user.id,
            action="staff.invitation.accept",
            entity_type="admin_invitation",
            entity_id=str(invitation.id),
            after_json=jsonable_encoder(
                {
                    "email": invitation.email,
                    "role_codes": invitation.role_codes,
                    "accepted_at": now,
                }
            ),
            context_json={"source": "email_invitation"},
            ip_address=client_ip_from_request(request),
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
            request_id=(request.headers.get("x-request-id") or "")[:120] or None,
        )
    )
    await db.commit()
    return AdminInvitationAcceptResponse(email=invitation.email)
