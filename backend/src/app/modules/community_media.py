from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import FileResponse

from src.app.services.community import blocked_community_author_ids, resolve_community_media_path, verify_community_media_signature
from src.database.models import CommunityAttachment, CommunityMessage, User
from src.database import get_db

community_media_router = APIRouter(prefix="/community-media", tags=["community_media"])


@community_media_router.get("/{media_type}/{media_id}", name="get_community_media")
async def get_community_media(
    media_type: str,
    media_id: int,
    uid: int = Query(ge=1),
    expires: int = Query(ge=1),
    signature: str = Query(min_length=32, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    if not verify_community_media_signature(media_type=media_type, media_id=media_id, user_id=uid, expires=expires, signature=signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Community media link expired")
    user = await db.get(User, uid)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="Community media not found")
    blocked_ids = await blocked_community_author_ids(db, uid)
    author_id = media_id if media_type == "author" else None
    if media_type == "attachment":
        attachment = await db.get(CommunityAttachment, media_id)
        message = await db.get(CommunityMessage, attachment.message_id) if attachment else None
        if message is None or message.deleted_at:
            raise HTTPException(status_code=404, detail="Community media not found")
        author_id = message.author_id
    if author_id in blocked_ids:
        raise HTTPException(status_code=404, detail="Community media not found")
    resolved = await resolve_community_media_path(db, media_type=media_type, media_id=media_id)
    if resolved is None or not resolved[0].is_file(): raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Community media not found")
    path, media_type_hint = resolved
    return FileResponse(path, media_type=media_type_hint, headers={"Cache-Control": "private, max-age=300"})
