from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.database.schemas.community import (
    CommunityMarkReadPayload,
    CommunityMarkReadResponse,
    CommunityMessageEditPayload,
    CommunityMessagePageRead,
    CommunityMessageRead,
    CommunityReactionRead,
    CommunityReactionTogglePayload,
    CommunityStatusRead,
    CommunityTopicListRead,
)
from src.app.services.app_integrity import require_app_integrity
from src.app.services.community import (
    create_community_message,
    delete_community_message,
    edit_community_message,
    get_community_status,
    list_community_messages,
    list_community_topics,
    mark_community_topic_read,
    toggle_community_message_reaction,
)
from src.database import get_db
from src.database.models import User

community_router = APIRouter(prefix="/community", tags=["community"])


@community_router.get("/status", response_model=CommunityStatusRead, status_code=status.HTTP_200_OK)
async def get_my_community_status(
    request: Request,
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:read")),
) -> CommunityStatusRead:
    return await get_community_status(db, user=current_user, request=request, refresh=refresh)


@community_router.get("/topics", response_model=CommunityTopicListRead, status_code=status.HTTP_200_OK)
async def get_my_community_topics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:read")),
) -> CommunityTopicListRead:
    return await list_community_topics(db, user=current_user, request=request)


@community_router.get("/topics/{topic_id}/messages", response_model=CommunityMessagePageRead, status_code=status.HTTP_200_OK)
async def get_my_community_topic_messages(
    topic_id: int,
    request: Request,
    before_id: int | None = Query(default=None, ge=1),
    after_id: int | None = Query(default=None, ge=1),
    changed_after: datetime | None = Query(default=None),
    changed_after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:read")),
) -> CommunityMessagePageRead:
    return await list_community_messages(db, user=current_user, request=request, topic_id=topic_id, before_id=before_id, after_id=after_id, changed_after=changed_after, changed_after_id=changed_after_id, limit=limit)


@community_router.post("/topics/{topic_id}/messages", response_model=CommunityMessageRead, status_code=status.HTTP_202_ACCEPTED)
async def send_my_community_topic_message(
    topic_id: int,
    request: Request,
    client_id: str = Form(..., min_length=1, max_length=64),
    text: str = Form(default="", max_length=4096),
    reply_to_message_id: int | None = Form(default=None, ge=1),
    attachments: list[UploadFile] | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:send")),
) -> CommunityMessageRead:
    return await create_community_message(db, user=current_user, request=request, topic_id=topic_id, client_id=client_id.strip(), text=text, reply_to_message_id=reply_to_message_id, uploads=attachments or [])


@community_router.patch("/topics/{topic_id}/messages/{message_id}", response_model=CommunityMessageRead, status_code=status.HTTP_200_OK)
async def edit_my_community_topic_message(
    topic_id: int,
    message_id: int,
    payload: CommunityMessageEditPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:send")),
) -> CommunityMessageRead:
    return await edit_community_message(
        db,
        user=current_user,
        request=request,
        topic_id=topic_id,
        message_id=message_id,
        text=payload.text,
    )


@community_router.delete("/topics/{topic_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_community_topic_message(
    topic_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:send")),
) -> Response:
    await delete_community_message(db, user=current_user, topic_id=topic_id, message_id=message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@community_router.post("/topics/{topic_id}/read", response_model=CommunityMarkReadResponse, status_code=status.HTTP_200_OK)
async def mark_my_community_topic_read(
    topic_id: int,
    payload: CommunityMarkReadPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:read")),
) -> CommunityMarkReadResponse:
    await mark_community_topic_read(db, user=current_user, topic_id=topic_id, last_message_id=payload.last_message_id)
    return CommunityMarkReadResponse()


@community_router.post("/topics/{topic_id}/messages/{message_id}/reactions", response_model=list[CommunityReactionRead], status_code=status.HTTP_200_OK)
async def toggle_my_community_message_reaction(
    topic_id: int,
    message_id: int,
    payload: CommunityReactionTogglePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("community:send")),
) -> list[CommunityReactionRead]:
    return await toggle_community_message_reaction(db, user=current_user, topic_id=topic_id, message_id=message_id, emoji=payload.emoji)
