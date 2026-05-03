from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import AI_CHAT_MAX_AUDIO_BYTES
from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import (
    AIChatActionPayload,
    AIChatActionResponse,
    AIChatResponse,
    AIChatTranscriptionResponse,
    AIChatTurnMetaRead,
)
from src.app.services.app_integrity import require_app_integrity
from src.app.services.ai.chat import get_or_create_user_chat, perform_user_ai_chat_action, send_user_chat_message
from src.app.services.basket import _get_serialized_basket
from src.app.services.upload_limits import read_upload_file_limited
from src.database import get_db
from src.database.models import User
from src.integrations.ai import get_professor_client

if TYPE_CHECKING:
    from src.integrations.ai.client import ProfessorClient#

ai_chat_router = APIRouter(prefix="/ai-chat", tags=["ai_chat"])


@ai_chat_router.get("", response_model=AIChatResponse, status_code=status.HTTP_200_OK)
async def get_my_ai_chat(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    professor_client: "ProfessorClient" = Depends(get_professor_client),
    _app_integrity: None = Depends(require_app_integrity("ai-chat:read")),
) -> AIChatResponse:
    chat = await get_or_create_user_chat(db, user=current_user, professor_client=professor_client)
    return AIChatResponse(chat=chat, last_turn=None)


@ai_chat_router.post("", response_model=AIChatResponse, status_code=status.HTTP_200_OK)
async def send_my_ai_chat_message(
    request: Request,
    text: str = Form(...),
    attachments: list[UploadFile] | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    professor_client: "ProfessorClient" = Depends(get_professor_client),
    _app_integrity: None = Depends(require_app_integrity("ai-chat:send")),
) -> AIChatResponse:
    normalized_text = text.strip()
    if not normalized_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text must not be empty")

    result = await send_user_chat_message(
        db,
        user=current_user,
        text=normalized_text,
        attachments=attachments,
        professor_client=professor_client,
    )
    basket = await _get_serialized_basket(request, db, current_user.id) if result.basket_updated else None
    return AIChatResponse(chat=result.chat, last_turn=AIChatTurnMetaRead(**result.turn_meta), basket=basket)


@ai_chat_router.post("/actions", response_model=AIChatActionResponse, status_code=status.HTTP_200_OK)
async def perform_my_ai_chat_action(
    payload: AIChatActionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _app_integrity: None = Depends(require_app_integrity("ai-chat:action")),
) -> AIChatActionResponse:
    result = await perform_user_ai_chat_action(
        db,
        user=current_user,
        message_id=payload.message_id,
        action_id=payload.action_id,
        action_token=payload.action_token,
        quantity=payload.quantity,
    )
    basket = await _get_serialized_basket(request, db, current_user.id) if result.basket_updated else None
    return AIChatActionResponse(
        chat=result.chat,
        last_turn=None,
        basket=basket,
        basket_item_id=result.basket_item_id,
    )


@ai_chat_router.post("/transcribe", response_model=AIChatTranscriptionResponse, status_code=status.HTTP_200_OK)
async def transcribe_my_ai_chat_voice_message(
    audio: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
    professor_client: "ProfessorClient" = Depends(get_professor_client),
    _app_integrity: None = Depends(require_app_integrity("ai-chat:transcribe")),
) -> AIChatTranscriptionResponse:
    content = await read_upload_file_limited(
        audio,
        max_bytes=AI_CHAT_MAX_AUDIO_BYTES,
        label="Audio upload",
    )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="audio must not be empty")

    filename = (audio.filename or "voice.m4a").strip() or "voice.m4a"
    text = await professor_client.transcribe_audio_bytes(filename=filename, content=content)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="audio could not be transcribed",
        )

    return AIChatTranscriptionResponse(text=text)
