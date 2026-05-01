from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import AIChatResponse, AIChatTranscriptionResponse, AIChatTurnMetaRead
from src.app.services.ai_chat import get_or_create_user_chat, send_user_chat_message
from src.database import get_db
from src.database.models import User
from src.integrations.ai import ProfessorClient, get_professor_client

ai_chat_router = APIRouter(prefix="/ai-chat", tags=["ai_chat"])


@ai_chat_router.get("", response_model=AIChatResponse, status_code=status.HTTP_200_OK)
async def get_my_ai_chat(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    professor_client: ProfessorClient = Depends(get_professor_client),
) -> AIChatResponse:
    chat = await get_or_create_user_chat(db, user=current_user, professor_client=professor_client)
    return AIChatResponse(chat=chat, last_turn=None)


@ai_chat_router.post("", response_model=AIChatResponse, status_code=status.HTTP_200_OK)
async def send_my_ai_chat_message(
    text: str = Form(...),
    attachments: list[UploadFile] | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    professor_client: ProfessorClient = Depends(get_professor_client),
) -> AIChatResponse:
    normalized_text = text.strip()
    if not normalized_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text must not be empty")

    chat, turn_meta = await send_user_chat_message(
        db,
        user=current_user,
        text=normalized_text,
        attachments=attachments,
        professor_client=professor_client,
    )
    return AIChatResponse(chat=chat, last_turn=AIChatTurnMetaRead(**turn_meta))


@ai_chat_router.post("/transcribe", response_model=AIChatTranscriptionResponse, status_code=status.HTTP_200_OK)
async def transcribe_my_ai_chat_voice_message(
    audio: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
    professor_client: ProfessorClient = Depends(get_professor_client),
) -> AIChatTranscriptionResponse:
    content = await audio.read()
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
