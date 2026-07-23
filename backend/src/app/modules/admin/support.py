from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import FileResponse

from config import ufa_now
from src.app.modules.admin.helpers import ensure_not_stale
from src.app.modules.admin.schemas import (
    AdminPage,
    AdminSupportConversationDetail,
    AdminSupportConversationRead,
    AdminSupportConversationUpdatePayload,
    AdminSupportMessagePayload,
    AdminSupportReadResponse,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission, resolve_admin_alert
from src.app.services.support import (
    add_admin_support_message,
    apply_conversation_sla,
    conversation_list_options,
    get_support_conversation,
    mark_support_read,
    send_support_reply_notification,
    serialize_support_conversation,
)
from src.database import get_db
from src.database.models import (
    Admin,
    CrmAssignmentHistory,
    CrmConversation,
    CrmMessage,
    CrmMessageAttachment,
    Order,
    User,
)

admin_support_router = APIRouter(prefix="/support", tags=["admin_support"])


async def _last_message_preview(db: AsyncSession, conversation_ids: list[int]) -> dict[int, str]:
    if not conversation_ids:
        return {}
    ranked = (
        select(
            CrmMessage.conversation_id.label("conversation_id"),
            CrmMessage.body.label("body"),
            func.row_number().over(
                partition_by=CrmMessage.conversation_id,
                order_by=CrmMessage.id.desc(),
            ).label("row_number"),
        )
        .where(
            CrmMessage.conversation_id.in_(conversation_ids),
            CrmMessage.is_internal.is_(False),
        )
        .subquery()
    )
    rows = (await db.execute(
        select(ranked.c.conversation_id, ranked.c.body).where(ranked.c.row_number == 1)
    )).all()
    return {int(conversation_id): str(body or "")[:240] for conversation_id, body in rows}


@admin_support_router.get("/conversations", response_model=AdminPage[AdminSupportConversationRead])
async def list_support_conversations(
    q: str | None = Query(default=None, max_length=120),
    conversation_status: str | None = Query(default=None, alias="status", pattern="^(all|active|new|open|waiting_customer|waiting_team|resolved|spam)$"),
    priority: str | None = Query(default=None, pattern="^(low|normal|high|urgent)$"),
    assignee_user_id: int | None = Query(default=None, ge=1),
    unread: bool | None = None,
    sla_breached: bool | None = None,
    customer_user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("support.read")),
) -> AdminPage[AdminSupportConversationRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            CrmConversation.subject.ilike(pattern),
            CrmConversation.customer.has(
                or_(
                    func.concat_ws(" ", User.name, User.surname).ilike(pattern),
                    User.email.ilike(pattern),
                    User.phone_number.ilike(pattern),
                )
            ),
        ))
    if conversation_status == "active":
        filters.append(CrmConversation.status.in_(("new", "open", "waiting_customer", "waiting_team")))
    elif conversation_status and conversation_status != "all":
        filters.append(CrmConversation.status == conversation_status)
    if priority:
        filters.append(CrmConversation.priority == priority)
    if assignee_user_id:
        filters.append(CrmConversation.assignee_user_id == assignee_user_id)
    if unread is True:
        filters.append(CrmConversation.admin_unread_count > 0)
    if sla_breached is True:
        filters.append(CrmConversation.sla_breached_at.is_not(None))
    if customer_user_id:
        filters.append(CrmConversation.customer_user_id == customer_user_id)

    total = int((await db.execute(select(func.count(CrmConversation.id)).where(*filters))).scalar_one())
    conversations = list((await db.execute(
        select(CrmConversation)
        .options(*conversation_list_options())
        .where(*filters)
        .order_by(
            CrmConversation.status.in_(("resolved", "spam")),
            (CrmConversation.admin_unread_count > 0).desc(),
            CrmConversation.last_message_at.desc().nullslast(),
            CrmConversation.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )).scalars().unique().all())
    previews = await _last_message_preview(db, [conversation.id for conversation in conversations])
    return AdminPage(
        items=[
            AdminSupportConversationRead.model_validate(
                serialize_support_conversation(
                    conversation,
                    admin_view=True,
                    include_messages=False,
                    last_message_preview=previews.get(conversation.id),
                )
            )
            for conversation in conversations
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_support_router.get("/conversations/{conversation_id}", response_model=AdminSupportConversationDetail)
async def get_support_conversation_detail(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("support.read")),
) -> AdminSupportConversationDetail:
    conversation = await get_support_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    return AdminSupportConversationDetail.model_validate(
        serialize_support_conversation(conversation, admin_view=True, include_messages=True)
    )


@admin_support_router.post("/conversations/{conversation_id}/read", response_model=AdminSupportReadResponse)
async def mark_support_conversation_read(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("support.read")),
) -> AdminSupportReadResponse:
    conversation = await get_support_conversation(db, conversation_id, lock=True)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    await mark_support_read(db, conversation=conversation, reader="admin")
    return AdminSupportReadResponse(conversation_id=conversation.id, unread_count=0)


@admin_support_router.post("/conversations/{conversation_id}/messages", response_model=AdminSupportConversationDetail)
async def reply_to_support_conversation(
    conversation_id: int,
    payload: AdminSupportMessagePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("support.reply", write=True)),
) -> AdminSupportConversationDetail:
    conversation = await get_support_conversation(db, conversation_id, lock=True)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    message = await add_admin_support_message(
        db,
        conversation=conversation,
        admin_user_id=context.user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="support.note" if payload.is_internal else "support.reply",
        entity_type="support_conversation",
        entity_id=conversation.id,
        after={"message_id": message.id, "is_internal": payload.is_internal},
    )
    await db.commit()
    if not payload.is_internal:
        admin_name = f"{context.user.name} {context.user.surname}".strip()
        await send_support_reply_notification(
            db,
            conversation=conversation,
            message=message,
            admin_name=admin_name,
        )
    refreshed = await get_support_conversation(db, conversation.id)
    if refreshed is None:
        raise RuntimeError("Support conversation could not be reloaded")
    return AdminSupportConversationDetail.model_validate(
        serialize_support_conversation(refreshed, admin_view=True, include_messages=True)
    )


@admin_support_router.patch("/conversations/{conversation_id}", response_model=AdminSupportConversationDetail)
async def update_support_conversation(
    conversation_id: int,
    payload: AdminSupportConversationUpdatePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("support.assign", write=True)),
) -> AdminSupportConversationDetail:
    conversation = await get_support_conversation(db, conversation_id, lock=True)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    ensure_not_stale(actual=conversation.updated_at, expected=payload.expected_updated_at)
    before = serialize_support_conversation(conversation, admin_view=True, include_messages=False)
    values = payload.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    if "assignee_user_id" in values and values["assignee_user_id"] is not None:
        assignee = await db.get(Admin, values["assignee_user_id"])
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assignee is not an active administrator")
    if "order_id" in values and values["order_id"] is not None:
        order = await db.get(Order, values["order_id"])
        if order is None or order.user_id != conversation.customer_user_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order does not belong to this customer")

    previous_assignee = conversation.assignee_user_id
    previous_priority = conversation.priority
    for field, value in values.items():
        if field == "subject" and isinstance(value, str):
            value = value.strip() or None
        setattr(conversation, field, value)
    now = ufa_now()
    if conversation.assignee_user_id != previous_assignee:
        db.add(CrmAssignmentHistory(
            conversation_id=conversation.id,
            from_admin_user_id=previous_assignee,
            to_admin_user_id=conversation.assignee_user_id,
            changed_by_user_id=context.user.id,
        ))
    if conversation.priority != previous_priority:
        await apply_conversation_sla(db, conversation, origin=conversation.created_at)
        conversation.sla_breached_at = None
    if conversation.status in {"resolved", "spam"}:
        conversation.resolved_at = conversation.resolved_at or now
        await resolve_admin_alert(
            db,
            fingerprint=f"sla:support:{conversation.id}",
            resolved_by_user_id=context.user.id,
        )
    elif conversation.status not in {"spam"}:
        conversation.resolved_at = None
    await db.flush()
    await add_admin_audit(
        db,
        request,
        context,
        action="support.update",
        entity_type="support_conversation",
        entity_id=conversation.id,
        before=before,
        after=serialize_support_conversation(conversation, admin_view=True, include_messages=False),
    )
    await db.commit()
    refreshed = await get_support_conversation(db, conversation.id)
    if refreshed is None:
        raise RuntimeError("Support conversation could not be reloaded")
    return AdminSupportConversationDetail.model_validate(
        serialize_support_conversation(refreshed, admin_view=True, include_messages=True)
    )


@admin_support_router.get("/attachments/{attachment_id}")
async def download_support_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("support.read")),
) -> FileResponse:
    attachment = (await db.execute(
        select(CrmMessageAttachment)
        .options(joinedload(CrmMessageAttachment.message))
        .where(CrmMessageAttachment.id == attachment_id)
    )).scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support attachment not found")
    path = Path(attachment.path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support attachment file not found")
    return FileResponse(
        path,
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
        headers={"Cache-Control": "private, no-store"},
    )
