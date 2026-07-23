from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import FileResponse

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import (
    SupportConversationRead,
    SupportInboxRead,
    SupportReadResponse,
)
from src.app.modules.users.me.schemas.support import SupportConversationCreatePayload
from src.app.services.app_integrity import require_app_integrity
from src.app.services.support import (
    ACTIVE_CONVERSATION_STATUSES,
    add_user_support_message,
    create_support_conversation,
    get_active_support_conversation,
    get_support_conversation,
    mark_support_read,
    conversation_list_options,
    serialize_support_conversation,
    support_unread_count,
)
from src.database import get_db
from src.database.models import CrmConversation, CrmMessage, CrmMessageAttachment, User

support_router = APIRouter(prefix="/support", tags=["support"])


@support_router.get("", response_model=SupportInboxRead)
async def get_my_support_inbox(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:read")),
) -> SupportInboxRead:
    active = await get_active_support_conversation(db, user_id=current_user.id)
    previous = list((await db.execute(
        select(CrmConversation)
        .options(*conversation_list_options())
        .where(
            CrmConversation.customer_user_id == current_user.id,
            CrmConversation.status.notin_(ACTIVE_CONVERSATION_STATUSES),
        )
        .order_by(CrmConversation.id.desc())
        .limit(20)
    )).scalars().unique().all())
    return SupportInboxRead(
        active=serialize_support_conversation(active, admin_view=False, include_messages=True) if active else None,
        previous=[
            serialize_support_conversation(item, admin_view=False, include_messages=False)
            for item in previous
        ],
        total_unread=await support_unread_count(db, user_id=current_user.id),
    )


@support_router.post("/conversations", response_model=SupportConversationRead, status_code=status.HTTP_201_CREATED)
async def create_my_support_conversation(
    payload: SupportConversationCreatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:write")),
) -> SupportConversationRead:
    conversation = await create_support_conversation(
        db,
        user_id=current_user.id,
        subject=payload.subject,
        body=payload.message,
        client_message_id=payload.client_message_id,
    )
    return SupportConversationRead.model_validate(
        serialize_support_conversation(conversation, admin_view=False, include_messages=True)
    )


@support_router.get("/conversations/{conversation_id}", response_model=SupportConversationRead)
async def get_my_support_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:read")),
) -> SupportConversationRead:
    conversation = await get_support_conversation(db, conversation_id, user_id=current_user.id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    return SupportConversationRead.model_validate(
        serialize_support_conversation(conversation, admin_view=False, include_messages=True)
    )


@support_router.post("/conversations/{conversation_id}/messages", response_model=SupportConversationRead)
async def send_my_support_message(
    conversation_id: int,
    client_message_id: UUID = Form(...),
    message: str = Form(default="", max_length=8000),
    attachments: list[UploadFile] | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:write")),
) -> SupportConversationRead:
    conversation = await add_user_support_message(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        body=message,
        client_message_id=client_message_id,
        uploads=attachments,
    )
    return SupportConversationRead.model_validate(
        serialize_support_conversation(conversation, admin_view=False, include_messages=True)
    )


@support_router.post("/conversations/{conversation_id}/read", response_model=SupportReadResponse)
async def mark_my_support_conversation_read(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:write")),
) -> SupportReadResponse:
    conversation = await get_support_conversation(db, conversation_id, user_id=current_user.id, lock=True)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support conversation not found")
    await mark_support_read(db, conversation=conversation, reader="customer")
    return SupportReadResponse(conversation_id=conversation.id, unread_count=0)


@support_router.get("/attachments/{attachment_id}")
async def download_my_support_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("support:read")),
) -> FileResponse:
    attachment = (await db.execute(
        select(CrmMessageAttachment)
        .options(joinedload(CrmMessageAttachment.message))
        .join(CrmMessage, CrmMessage.id == CrmMessageAttachment.message_id)
        .join(CrmConversation, CrmConversation.id == CrmMessage.conversation_id)
        .where(
            CrmMessageAttachment.id == attachment_id,
            CrmConversation.customer_user_id == current_user.id,
            CrmMessage.is_internal.is_(False),
        )
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
