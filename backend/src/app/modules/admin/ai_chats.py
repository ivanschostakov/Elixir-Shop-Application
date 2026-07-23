from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse
from starlette import status

from src.app.modules.admin.schemas import (
    AdminAIChatActionRead,
    AdminAIChatDetail,
    AdminAIChatListItem,
    AdminAIChatMessageRead,
    AdminPage,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.crud.ai.chat import get_ai_chat_by_id
from src.database.models import AIChat, AIMessage, Attachment, User, UserEvent
from src.integrations.ai.enums import MessageSender

admin_ai_chats_router = APIRouter(prefix="/ai-chats", tags=["admin_ai_chats"])
AI_CHAT_EVENT_NAMES = (
    "ai_chat_message_sent",
    "ai_recommendation_shown",
    "ai_action_clicked",
    "ai_action_completed",
)


def _safe_ai_context(value: dict[str, Any] | None) -> dict[str, Any]:
    def sanitize(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: sanitize(child)
                for key, child in item.items()
                if key not in {"action_token"}
            }
        if isinstance(item, list):
            return [sanitize(child) for child in item]
        return item

    return sanitize(deepcopy(value or {}))


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


@admin_ai_chats_router.get("", response_model=AdminPage[AdminAIChatListItem])
async def list_ai_chats(
    q: str | None = Query(default=None, max_length=120),
    user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("ai_chats.read")),
) -> AdminPage[AdminAIChatListItem]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            func.concat_ws(" ", User.name, User.surname).ilike(pattern),
            User.email.ilike(pattern),
            User.phone_number.ilike(pattern),
            AIChat.messages.any(AIMessage.text.ilike(pattern)),
        ))
    if user_id:
        filters.append(AIChat.user_id == user_id)
    message_stats = (
        select(
            AIMessage.chat_id.label("chat_id"),
            func.count(AIMessage.id).label("messages_count"),
            func.sum(case((AIMessage.sender == MessageSender.USER, 1), else_=0)).label("user_messages_count"),
            func.max(AIMessage.created_at).label("last_activity_at"),
        )
        .group_by(AIMessage.chat_id)
        .subquery()
    )
    last_message = (
        select(AIMessage.text)
        .where(AIMessage.chat_id == AIChat.id)
        .order_by(AIMessage.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    total = int((await db.execute(
        select(func.count(AIChat.id)).join(User, User.id == AIChat.user_id).where(*filters)
    )).scalar_one())
    rows = (await db.execute(
        select(
            AIChat,
            User,
            func.coalesce(message_stats.c.messages_count, 0),
            func.coalesce(message_stats.c.user_messages_count, 0),
            func.coalesce(message_stats.c.last_activity_at, AIChat.updated_at),
            last_message.label("last_message"),
        )
        .join(User, User.id == AIChat.user_id)
        .outerjoin(message_stats, message_stats.c.chat_id == AIChat.id)
        .where(*filters)
        .order_by(func.coalesce(message_stats.c.last_activity_at, AIChat.updated_at).desc(), AIChat.id.desc())
        .offset(offset)
        .limit(limit)
    )).all()
    return AdminPage(
        items=[
            AdminAIChatListItem(
                id=chat.id,
                user_id=chat.user_id,
                customer_name=f"{user.name} {user.surname}".strip(),
                customer_email=user.email,
                messages_count=int(messages_count or 0),
                user_messages_count=int(user_messages_count or 0),
                total_tokens=chat.total_tokens,
                last_message=str(last_message_text or "")[:240] or None,
                last_activity_at=last_activity_at,
                created_at=chat.created_at,
            )
            for chat, user, messages_count, user_messages_count, last_activity_at, last_message_text in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_ai_chats_router.get("/attachments/{attachment_id}")
async def download_ai_chat_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("ai_chats.read")),
) -> FileResponse:
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI chat attachment not found")
    path = Path(attachment.path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI chat attachment file not found")
    return FileResponse(
        path,
        media_type=attachment.mime_type or "application/octet-stream",
        filename=attachment.original_filename or attachment.filename,
        headers={"Cache-Control": "private, no-store"},
    )


@admin_ai_chats_router.get("/{chat_id}", response_model=AdminAIChatDetail)
async def get_ai_chat_detail(
    chat_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("ai_chats.read")),
) -> AdminAIChatDetail:
    chat = await get_ai_chat_by_id(db, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI chat not found")
    user = await db.get(User, chat.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI chat customer not found")
    action_events = list((await db.execute(
        select(UserEvent)
        .where(
            UserEvent.user_id == chat.user_id,
            UserEvent.event_name.in_(AI_CHAT_EVENT_NAMES),
            UserEvent.occurred_at >= chat.created_at,
        )
        .order_by(UserEvent.occurred_at, UserEvent.id)
        .limit(1000)
    )).scalars().all())
    result = AdminAIChatDetail(
        id=chat.id,
        user_id=chat.user_id,
        customer_name=f"{user.name} {user.surname}".strip(),
        customer_email=user.email,
        customer_phone=user.phone_number,
        conversation_id=chat.conversation_id,
        current_tokens=chat.current_tokens,
        total_tokens=chat.total_tokens,
        messages=[
            AdminAIChatMessageRead(
                id=message.id,
                sender=str(getattr(message.sender, "value", message.sender)),
                text=message.text,
                context=_safe_ai_context(message.context_json),
                attachments=[
                    {
                        "id": attachment.id,
                        "name": attachment.original_filename or attachment.filename,
                        "mime_type": attachment.mime_type,
                        "size_bytes": attachment.size_bytes,
                        "url": f"/api/v1/admin/ai-chats/attachments/{attachment.id}",
                    }
                    for attachment in message.attachments
                ],
                usage={
                    "input_tokens": message.usage.input_tokens,
                    "cached_input_tokens": message.usage.cached_input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "bot_model": str(getattr(message.usage.bot_model, "value", message.usage.bot_model)),
                    "openai_model": message.usage.openai_model,
                } if message.usage else None,
                created_at=message.created_at,
            )
            for message in chat.messages
        ],
        actions=[
            AdminAIChatActionRead(
                id=event.id,
                event_name=event.event_name,
                source=event.source,
                message_id=(
                    event.entity_id
                    if event.entity_type == "ai_message"
                    else _optional_int((event.properties_json or {}).get("message_id"))
                ),
                action_id=(
                    str((event.properties_json or {}).get("action_id"))
                    if (event.properties_json or {}).get("action_id") is not None
                    else None
                ),
                action_type=(
                    str((event.properties_json or {}).get("action_type"))
                    if (event.properties_json or {}).get("action_type") is not None
                    else None
                ),
                product_id=_optional_int((event.properties_json or {}).get("product_id")),
                variant_id=_optional_int((event.properties_json or {}).get("variant_id")),
                basket_item_id=_optional_int((event.properties_json or {}).get("basket_item_id")),
                properties=_safe_ai_context(event.properties_json),
                occurred_at=event.occurred_at,
            )
            for event in action_events
        ],
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="ai_chat.read",
        entity_type="ai_chat",
        entity_id=chat.id,
        details={"customer_user_id": chat.user_id},
    )
    await db.commit()
    return result
