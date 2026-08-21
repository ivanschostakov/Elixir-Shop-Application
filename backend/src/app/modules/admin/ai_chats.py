from copy import deepcopy
from datetime import timedelta
import ipaddress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse
from starlette import status

from src.app.modules.admin.schemas import (
    AdminAIChatActionRead,
    AdminAIChatBanCreate,
    AdminAIChatBanPage,
    AdminAIChatBanRead,
    AdminAIChatDetail,
    AdminAIChatListItem,
    AdminAIChatMessageRead,
    AdminAIChatSecurityEventPage,
    AdminAIChatSecurityEventRead,
    AdminAIChatSecurityOverview,
    AdminAIChatSecuritySourceSummary,
    AdminPage,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.admin.alerts import raise_admin_alert, resolve_admin_alert
from src.app.services.ai.bitrix_admin import BitrixAIAdminError, bitrix_ai_admin_client, bitrix_ai_admin_configured
from config import ufa_now
from src.database import get_db
from src.database.crud.ai.chat import get_ai_chat_by_id
from src.database.models import AIChat, AIChatAccessBan, AIChatSecurityEvent, AIMessage, Attachment, User, UserEvent
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


def _app_security_event_read(row: AIChatSecurityEvent, user: User) -> AdminAIChatSecurityEventRead:
    return AdminAIChatSecurityEventRead(
        id=row.id,
        source="app",
        event_type=row.event_type,
        outcome=row.outcome,
        account_id=str(row.user_id),
        email_address=user.email,
        display_name=f"{user.name} {user.surname}".strip() or None,
        ip_address=row.ip_address,
        risk_score=row.risk_score,
        is_suspicious=row.is_suspicious,
        risk_reasons=row.risk_reasons or [],
        details=row.details_json or {},
        created_at=row.created_at,
    )


def _app_ban_read(row: AIChatAccessBan) -> AdminAIChatBanRead:
    return AdminAIChatBanRead(
        id=row.id,
        source="app",
        ban_type=row.ban_type,
        subject=row.subject,
        reason=row.reason,
        is_active=row.is_active,
        created_by=str(row.created_by_user_id) if row.created_by_user_id else None,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        revoked_by=str(row.revoked_by_user_id) if row.revoked_by_user_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _app_security_summary(db: AsyncSession) -> AdminAIChatSecuritySourceSummary:
    since = ufa_now() - timedelta(hours=24)
    events, messages, suspicious = (await db.execute(select(
        func.count(AIChatSecurityEvent.id),
        func.count(AIChatSecurityEvent.id).filter(AIChatSecurityEvent.event_type == "message_requested"),
        func.count(AIChatSecurityEvent.id).filter(AIChatSecurityEvent.is_suspicious.is_(True)),
    ).where(AIChatSecurityEvent.created_at >= since))).one()
    active_bans = int((await db.execute(select(func.count(AIChatAccessBan.id)).where(
        AIChatAccessBan.is_active.is_(True),
        or_(AIChatAccessBan.expires_at.is_(None), AIChatAccessBan.expires_at > ufa_now()),
    ))).scalar_one())
    return AdminAIChatSecuritySourceSummary(
        source="app",
        events=int(events or 0),
        messages=int(messages or 0),
        suspicious=int(suspicious or 0),
        active_bans=active_bans,
    )


@admin_ai_chats_router.get("/security/overview", response_model=AdminAIChatSecurityOverview)
async def ai_chat_security_overview(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("ai_chats.read")),
) -> AdminAIChatSecurityOverview:
    app_summary = await _app_security_summary(db)
    bitrix_summary = AdminAIChatSecuritySourceSummary(source="bitrix", configured=bitrix_ai_admin_configured())
    if bitrix_ai_admin_configured():
        try:
            bitrix_summary = AdminAIChatSecuritySourceSummary.model_validate(
                await bitrix_ai_admin_client.request("GET", "/summary")
            )
            if bitrix_summary.suspicious:
                await raise_admin_alert(
                    db,
                    severity="warning",
                    source="ai_security",
                    code="suspicious_bitrix_ai_chat_activity",
                    title_ru="Подозрительная активность в Bitrix AI-чате",
                    title_en="Suspicious Bitrix AI chat activity",
                    message=f"За последние 24 часа обнаружено подозрительных событий: {bitrix_summary.suspicious}.",
                    fingerprint="ai-security:bitrix:aggregate",
                    entity_type="ai_chat_source",
                    entity_id="bitrix",
                    path="/communications?tab=ai&security=1",
                )
            else:
                await resolve_admin_alert(db, fingerprint="ai-security:bitrix:aggregate")
            await db.commit()
        except BitrixAIAdminError as exc:
            bitrix_summary = AdminAIChatSecuritySourceSummary(
                source="bitrix",
                configured=True,
                error=str(exc),
            )
    return AdminAIChatSecurityOverview(app=app_summary, bitrix=bitrix_summary)


@admin_ai_chats_router.get("/security/activity", response_model=AdminAIChatSecurityEventPage)
async def ai_chat_security_activity(
    source: str = Query(default="app", pattern="^(app|bitrix)$"),
    suspicious_only: bool = False,
    q: str | None = Query(default=None, max_length=190),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("ai_chats.read")),
) -> AdminAIChatSecurityEventPage:
    if source == "bitrix":
        try:
            return AdminAIChatSecurityEventPage.model_validate(await bitrix_ai_admin_client.request(
                "GET",
                "/activity",
                params={"suspicious_only": suspicious_only, "q": q, "limit": limit, "offset": offset},
            ))
        except BitrixAIAdminError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    filters = []
    if suspicious_only:
        filters.append(AIChatSecurityEvent.is_suspicious.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(
            User.email.ilike(pattern),
            User.name.ilike(pattern),
            User.surname.ilike(pattern),
            AIChatSecurityEvent.ip_address.ilike(pattern),
        ))
    total = int((await db.execute(select(func.count(AIChatSecurityEvent.id)).join(
        User, User.id == AIChatSecurityEvent.user_id
    ).where(*filters))).scalar_one())
    rows = (await db.execute(select(AIChatSecurityEvent, User).join(
        User, User.id == AIChatSecurityEvent.user_id
    ).where(*filters).order_by(
        AIChatSecurityEvent.created_at.desc(), AIChatSecurityEvent.id.desc()
    ).offset(offset).limit(limit))).all()
    return AdminAIChatSecurityEventPage(
        items=[_app_security_event_read(row, user) for row, user in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_ai_chats_router.get("/security/bans", response_model=AdminAIChatBanPage)
async def ai_chat_security_bans(
    source: str = Query(default="app", pattern="^(app|bitrix)$"),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("ai_chats.read")),
) -> AdminAIChatBanPage:
    if source == "bitrix":
        try:
            return AdminAIChatBanPage.model_validate(await bitrix_ai_admin_client.request(
                "GET", "/bans", params={"include_inactive": include_inactive}
            ))
        except BitrixAIAdminError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    filters = [] if include_inactive else [AIChatAccessBan.is_active.is_(True)]
    rows = list((await db.execute(select(AIChatAccessBan).where(*filters).order_by(
        AIChatAccessBan.created_at.desc(), AIChatAccessBan.id.desc()
    ))).scalars().all())
    return AdminAIChatBanPage(items=[_app_ban_read(row) for row in rows], total=len(rows), limit=len(rows), offset=0)


@admin_ai_chats_router.post("/security/bans", response_model=AdminAIChatBanRead)
async def create_ai_chat_ban(
    payload: AdminAIChatBanCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("ai_chats.manage", write=True)),
) -> AdminAIChatBanRead:
    if payload.expires_at and payload.expires_at <= ufa_now():
        raise HTTPException(status_code=422, detail="expires_at must be in the future")
    if payload.source == "bitrix":
        try:
            result = AdminAIChatBanRead.model_validate(await bitrix_ai_admin_client.request(
                "POST",
                "/bans",
                json={
                    "ban_type": payload.ban_type,
                    "subject": payload.subject,
                    "reason": payload.reason,
                    "created_by": context.user.email,
                    "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
                },
            ))
        except BitrixAIAdminError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await add_admin_audit(db, request, context, action="ai_chat.ban.create", entity_type="bitrix_ai_ban", entity_id=result.id, after=result.model_dump(mode="json"))
        await db.commit()
        return result

    subject = payload.subject.strip()
    if payload.ban_type == "ip":
        try:
            subject = str(ipaddress.ip_address(subject))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid IP address") from exc
    else:
        if not subject.isdigit() or int(subject) <= 0:
            raise HTTPException(status_code=422, detail="Account subject must be a positive user ID")
        if await db.get(User, int(subject)) is None:
            raise HTTPException(status_code=404, detail="User not found")

    row = (await db.execute(select(AIChatAccessBan).where(
        AIChatAccessBan.ban_type == payload.ban_type,
        AIChatAccessBan.subject == subject,
        AIChatAccessBan.is_active.is_(True),
    ))).scalar_one_or_none()
    if row is None:
        row = AIChatAccessBan(
            ban_type=payload.ban_type,
            subject=subject,
            reason=payload.reason,
            created_by_user_id=context.user.id,
            expires_at=payload.expires_at,
        )
        db.add(row)
    else:
        row.reason = payload.reason
        row.created_by_user_id = context.user.id
        row.expires_at = payload.expires_at
    await db.flush()
    await add_admin_audit(db, request, context, action="ai_chat.ban.create", entity_type="ai_chat_ban", entity_id=row.id, after={"ban_type": row.ban_type, "subject": row.subject, "reason": row.reason})
    await db.commit()
    await db.refresh(row)
    return _app_ban_read(row)


@admin_ai_chats_router.post("/security/bans/{source}/{ban_id}/revoke", response_model=AdminAIChatBanRead)
async def revoke_ai_chat_ban(
    source: str,
    ban_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("ai_chats.manage", write=True)),
) -> AdminAIChatBanRead:
    if source == "bitrix":
        try:
            result = AdminAIChatBanRead.model_validate(await bitrix_ai_admin_client.request(
                "POST", f"/bans/{ban_id}/revoke", json={"revoked_by": context.user.email}
            ))
        except BitrixAIAdminError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await add_admin_audit(db, request, context, action="ai_chat.ban.revoke", entity_type="bitrix_ai_ban", entity_id=ban_id)
        await db.commit()
        return result
    if source != "app":
        raise HTTPException(status_code=422, detail="Invalid source")
    row = await db.get(AIChatAccessBan, ban_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ban not found")
    if row.is_active:
        row.is_active = False
        row.revoked_at = ufa_now()
        row.revoked_by_user_id = context.user.id
    await add_admin_audit(db, request, context, action="ai_chat.ban.revoke", entity_type="ai_chat_ban", entity_id=ban_id)
    await db.commit()
    await db.refresh(row)
    return _app_ban_read(row)


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
