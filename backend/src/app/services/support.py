from __future__ import annotations

from datetime import datetime, timedelta
import logging
import mimetypes
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload
from starlette import status

from config import (
    SUPPORT_MAX_ATTACHMENTS,
    SUPPORT_MAX_ATTACHMENT_BYTES,
    SUPPORT_MAX_TOTAL_ATTACHMENT_BYTES,
    SUPPORT_MEDIA_DIR,
    ufa_now,
)
from src.app.services.push_notifications import send_push_to_user
from src.app.services.upload_limits import read_upload_file_limited
from src.database.models import (
    Admin,
    AdminRoleAssignment,
    AdminSlaPolicy,
    CrmConversation,
    CrmMessage,
    CrmMessageAttachment,
    NotificationDispatch,
)

log = logging.getLogger(__name__)
ACTIVE_CONVERSATION_STATUSES = ("new", "open", "waiting_customer", "waiting_team")
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/gif",
    "image/heic",
    "image/heif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _admin_name(admin: Admin | None) -> str | None:
    if admin is None:
        return None
    return f"{admin.user.name} {admin.user.surname}".strip()


def _admin_role(admin: Admin | None) -> str | None:
    if admin is None or not admin.role_assignments:
        return None
    role = admin.role_assignments[0].role
    return role.name_ru or role.name_en


def conversation_detail_options():
    message_admin = (
        selectinload(CrmConversation.messages)
        .joinedload(CrmMessage.admin)
        .selectinload(Admin.role_assignments)
        .joinedload(AdminRoleAssignment.role)
    )
    return (
        joinedload(CrmConversation.customer),
        joinedload(CrmConversation.assignee).joinedload(Admin.user),
        joinedload(CrmConversation.order),
        selectinload(CrmConversation.messages).selectinload(CrmMessage.attachments),
        selectinload(CrmConversation.messages).joinedload(CrmMessage.user),
        selectinload(CrmConversation.messages).joinedload(CrmMessage.admin).joinedload(Admin.user),
        message_admin,
    )


def conversation_list_options():
    return (
        joinedload(CrmConversation.customer),
        joinedload(CrmConversation.assignee).joinedload(Admin.user),
        joinedload(CrmConversation.order),
    )


async def get_support_conversation(
    db: AsyncSession,
    conversation_id: int,
    *,
    user_id: int | None = None,
    lock: bool = False,
) -> CrmConversation | None:
    stmt = (
        select(CrmConversation)
        .options(*conversation_detail_options())
        .where(CrmConversation.id == conversation_id)
        .execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(CrmConversation.customer_user_id == user_id)
    if lock:
        stmt = stmt.with_for_update(of=CrmConversation)
    return (await db.execute(stmt)).scalars().unique().one_or_none()


async def get_active_support_conversation(db: AsyncSession, *, user_id: int) -> CrmConversation | None:
    return (await db.execute(
        select(CrmConversation)
        .options(*conversation_detail_options())
        .where(
            CrmConversation.customer_user_id == user_id,
            CrmConversation.channel == "app_support",
            CrmConversation.status.in_(ACTIVE_CONVERSATION_STATUSES),
        )
        .order_by(CrmConversation.id.desc())
        .limit(1)
    )).scalars().unique().one_or_none()


async def apply_conversation_sla(
    db: AsyncSession,
    conversation: CrmConversation,
    *,
    origin: datetime | None = None,
) -> AdminSlaPolicy | None:
    policy = (await db.execute(
        select(AdminSlaPolicy).where(
            AdminSlaPolicy.priority == conversation.priority,
            AdminSlaPolicy.is_enabled.is_(True),
        )
    )).scalar_one_or_none()
    if policy is None:
        conversation.sla_policy_id = None
        conversation.response_due_at = None
        conversation.resolution_due_at = None
        return None
    started_at = origin or conversation.created_at or ufa_now()
    conversation.sla_policy_id = policy.id
    conversation.response_due_at = started_at + timedelta(minutes=policy.response_minutes)
    conversation.resolution_due_at = started_at + timedelta(minutes=policy.resolution_minutes)
    return policy


def _attachment_download_url(attachment_id: int, *, admin: bool) -> str:
    if admin:
        return f"/api/v1/admin/support/attachments/{attachment_id}"
    return f"/api/v1/users/me/support/attachments/{attachment_id}"


def serialize_support_message(message: CrmMessage, *, admin_view: bool) -> dict[str, Any]:
    if message.sender_type == "user":
        author_name = f"{message.user.name} {message.user.surname}".strip() if message.user else "Клиент"
        author_role = None
        author_user_id = message.user_id
    elif message.sender_type == "admin":
        author_name = _admin_name(message.admin) or "Поддержка"
        author_role = _admin_role(message.admin) or "Поддержка"
        author_user_id = message.admin_user_id
    else:
        author_name = "Система"
        author_role = None
        author_user_id = None
    return {
        "id": message.id,
        "sender_type": message.sender_type,
        "body": message.body,
        "author_user_id": author_user_id,
        "author_name": author_name,
        "author_role": author_role,
        "is_internal": message.is_internal,
        "delivered_at": message.delivered_at,
        "read_at": message.read_at,
        "attachments": [
            {
                "id": attachment.id,
                "original_filename": attachment.original_filename,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "download_url": _attachment_download_url(attachment.id, admin=admin_view),
            }
            for attachment in message.attachments
        ],
        "created_at": message.created_at,
        "updated_at": message.updated_at,
    }


def serialize_support_conversation(
    conversation: CrmConversation,
    *,
    admin_view: bool,
    include_messages: bool,
    last_message_preview: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": conversation.id,
        "subject": conversation.subject,
        "status": conversation.status,
        "priority": conversation.priority,
        "assignee_name": _admin_name(conversation.assignee),
        "customer_unread_count": conversation.customer_unread_count,
        "last_message_at": conversation.last_message_at,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }
    if admin_view:
        data.update({
            "customer_user_id": conversation.customer_user_id,
            "customer_name": f"{conversation.customer.name} {conversation.customer.surname}".strip(),
            "customer_email": conversation.customer.email,
            "customer_phone": conversation.customer.phone_number,
            "assignee_user_id": conversation.assignee_user_id,
            "order_id": conversation.order_id,
            "order_code": conversation.order.order_code if conversation.order else None,
            "response_due_at": conversation.response_due_at,
            "resolution_due_at": conversation.resolution_due_at,
            "first_responded_at": conversation.first_responded_at,
            "resolved_at": conversation.resolved_at,
            "sla_breached_at": conversation.sla_breached_at,
            "admin_unread_count": conversation.admin_unread_count,
            "last_message_preview": last_message_preview,
        })
    if include_messages:
        data["messages"] = [
            serialize_support_message(message, admin_view=admin_view)
            for message in conversation.messages
            if admin_view or not message.is_internal
        ]
    return data


async def _prepare_support_attachments(uploads: list[UploadFile] | None) -> list[tuple[str, str, str, bytes]]:
    files = uploads or []
    if len(files) > SUPPORT_MAX_ATTACHMENTS:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=f"Maximum {SUPPORT_MAX_ATTACHMENTS} attachments")
    prepared: list[tuple[str, str, str, bytes]] = []
    total_bytes = 0
    for index, upload in enumerate(files, start=1):
        content = await read_upload_file_limited(
            upload,
            max_bytes=SUPPORT_MAX_ATTACHMENT_BYTES,
            label=f"Support attachment {index}",
        )
        if not content:
            continue
        total_bytes += len(content)
        if total_bytes > SUPPORT_MAX_TOTAL_ATTACHMENT_BYTES:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Support attachments exceed total limit")
        mime_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only image attachments are supported")
        original_filename = Path((upload.filename or f"image-{index}").strip()).name[:255] or f"image-{index}"
        extension = Path(original_filename).suffix.lower()
        if not extension:
            extension = mimetypes.guess_extension(mime_type) or ".bin"
        prepared.append((original_filename, f"{uuid4().hex}{extension[:16]}", mime_type, content))
    return prepared


async def _persist_support_attachments(
    db: AsyncSession,
    *,
    conversation_id: int,
    message: CrmMessage,
    prepared: list[tuple[str, str, str, bytes]],
) -> list[Path]:
    written_paths: list[Path] = []
    for original_filename, filename, mime_type, content in prepared:
        attachment = CrmMessageAttachment(
            message_id=message.id,
            original_filename=original_filename,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(content),
        )
        db.add(attachment)
        await db.flush()
        path = SUPPORT_MEDIA_DIR / str(conversation_id) / str(message.id) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as target:
            await target.write(content)
        written_paths.append(path)
    return written_paths


def cleanup_support_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            log.exception("Could not remove failed support attachment path=%s", path)


async def create_support_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    subject: str | None,
    body: str,
    client_message_id: UUID,
) -> CrmConversation:
    duplicate = (await db.execute(
        select(CrmMessage).where(
            CrmMessage.client_message_id == client_message_id,
            CrmMessage.user_id == user_id,
        )
    )).scalar_one_or_none()
    if duplicate is not None:
        existing_result = await get_support_conversation(db, duplicate.conversation_id, user_id=user_id)
        if existing_result is not None:
            return existing_result
    existing = await get_active_support_conversation(db, user_id=user_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active support conversation already exists")
    now = ufa_now()
    normalized_body = body.strip()
    conversation = CrmConversation(
        customer_user_id=user_id,
        subject=(subject or "").strip()[:240] or normalized_body[:120] or "Обращение в поддержку",
        status="new",
        priority="normal",
        last_message_at=now,
        admin_unread_count=1,
    )
    db.add(conversation)
    await db.flush()
    await apply_conversation_sla(db, conversation, origin=now)
    db.add(CrmMessage(
        conversation_id=conversation.id,
        sender_type="user",
        user_id=user_id,
        client_message_id=client_message_id,
        body=normalized_body,
        delivered_at=now,
    ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        concurrent = await get_active_support_conversation(db, user_id=user_id)
        if concurrent is not None:
            return concurrent
        raise
    result = await get_support_conversation(db, conversation.id, user_id=user_id)
    if result is None:
        raise RuntimeError("Created support conversation could not be reloaded")
    return result


async def add_user_support_message(
    db: AsyncSession,
    *,
    conversation_id: int,
    user_id: int,
    body: str,
    client_message_id: UUID,
    uploads: list[UploadFile] | None,
) -> CrmConversation:
    duplicate = (await db.execute(
        select(CrmMessage).where(
            CrmMessage.client_message_id == client_message_id,
            CrmMessage.user_id == user_id,
        )
    )).scalar_one_or_none()
    if duplicate is not None:
        result = await get_support_conversation(db, duplicate.conversation_id, user_id=user_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
        return result

    prepared = await _prepare_support_attachments(uploads)
    normalized_body = body.strip()
    if not normalized_body and not prepared:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message or attachment is required")
    conversation = await get_support_conversation(db, conversation_id, user_id=user_id, lock=True)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    if conversation.status in {"resolved", "spam"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Support conversation is closed")

    now = ufa_now()
    message = CrmMessage(
        conversation_id=conversation.id,
        sender_type="user",
        user_id=user_id,
        client_message_id=client_message_id,
        body=normalized_body,
        delivered_at=now,
    )
    db.add(message)
    await db.flush()
    written_paths: list[Path] = []
    try:
        written_paths = await _persist_support_attachments(
            db,
            conversation_id=conversation.id,
            message=message,
            prepared=prepared,
        )
        conversation.last_message_at = now
        conversation.admin_unread_count += 1
        if conversation.first_responded_at is not None:
            conversation.status = "waiting_team"
        await db.commit()
    except Exception:
        await db.rollback()
        cleanup_support_files(written_paths)
        raise
    result = await get_support_conversation(db, conversation.id, user_id=user_id)
    if result is None:
        raise RuntimeError("Support conversation could not be reloaded")
    return result


async def add_admin_support_message(
    db: AsyncSession,
    *,
    conversation: CrmConversation,
    admin_user_id: int,
    body: str,
    is_internal: bool,
) -> CrmMessage:
    if conversation.status in {"resolved", "spam"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Support conversation is closed")
    now = ufa_now()
    message = CrmMessage(
        conversation_id=conversation.id,
        sender_type="admin",
        admin_user_id=admin_user_id,
        body=body.strip(),
        is_internal=is_internal,
        delivered_at=now,
    )
    db.add(message)
    if not is_internal:
        conversation.last_message_at = now
        conversation.customer_unread_count += 1
        conversation.admin_unread_count = 0
        conversation.admin_last_read_at = now
        conversation.status = "waiting_customer"
        if conversation.first_responded_at is None:
            conversation.first_responded_at = now
    await db.flush()
    return message


async def mark_support_read(
    db: AsyncSession,
    *,
    conversation: CrmConversation,
    reader: str,
) -> int:
    now = ufa_now()
    if reader == "customer":
        conversation.customer_unread_count = 0
        conversation.customer_last_read_at = now
        unread_sender = "admin"
    else:
        conversation.admin_unread_count = 0
        conversation.admin_last_read_at = now
        unread_sender = "user"
    messages = list((await db.execute(
        select(CrmMessage).where(
            CrmMessage.conversation_id == conversation.id,
            CrmMessage.sender_type == unread_sender,
            CrmMessage.is_internal.is_(False),
            CrmMessage.read_at.is_(None),
        )
    )).scalars().all())
    for message in messages:
        message.read_at = now
    await db.commit()
    return len(messages)


async def send_support_reply_notification(
    db: AsyncSession,
    *,
    conversation: CrmConversation,
    message: CrmMessage,
    admin_name: str,
) -> None:
    if message.is_internal:
        return
    try:
        sent_at = ufa_now()
        sent = await send_push_to_user(
            db,
            user_id=conversation.customer_user_id,
            title=f"{admin_name} · Поддержка",
            body=(message.body or "Новое сообщение от поддержки")[:180],
            data={
                "type": "support_reply",
                "conversation_id": conversation.id,
                "message_id": message.id,
            },
            channel_id="support_messages",
        )
        if sent:
            db.add(NotificationDispatch(
                user_id=conversation.customer_user_id,
                type="support_reply",
                dedupe_key=f"message:{message.id}",
                payload_json={"conversation_id": conversation.id, "message_id": message.id},
                sent_at=sent_at,
            ))
        await db.commit()
    except Exception:
        await db.rollback()
        log.exception(
            "Failed to send support reply notification conversation_id=%s message_id=%s",
            conversation.id,
            message.id,
        )


async def support_unread_count(db: AsyncSession, *, user_id: int) -> int:
    return int((await db.execute(
        select(func.coalesce(func.sum(CrmConversation.customer_unread_count), 0)).where(
            CrmConversation.customer_user_id == user_id
        )
    )).scalar_one())
