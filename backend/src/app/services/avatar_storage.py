from io import BytesIO
from pathlib import Path

import aiofiles
from fastapi import HTTPException, Request
from PIL import Image, UnidentifiedImageError
from starlette import status

from config import AVATARS_MEDIA_DIR

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AVATAR_EXTENSIONS = (".jpg", ".png", ".webp")
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024
AVATAR_EXTENSION = ".png"


def build_avatar_path(user_id: int) -> Path: return AVATARS_MEDIA_DIR / f"{user_id}{AVATAR_EXTENSION}"
def find_avatar_path(user_id: int) -> Path | None:
    candidate = build_avatar_path(user_id)
    if candidate.exists(): return candidate
    return None


def build_avatar_url(request: Request, image_path: Path | None) -> str | None:
    if image_path is None: return None
    base_url = str(request.base_url).rstrip("/")
    version = int(image_path.stat().st_mtime_ns)
    return f"{base_url}/media/avatars/{image_path.name}?v={version}"


def validate_avatar_content_type(content_type: str | None) -> None:
    if (content_type or "").lower() not in ALLOWED_AVATAR_TYPES: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG, PNG, and WEBP images are supported")


def validate_avatar_content(content: bytes) -> None:
    if not content: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty")
    if len(content) > MAX_AVATAR_SIZE_BYTES: raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Avatar image must be 5 MB or smaller")


def convert_avatar_to_png(content: bytes) -> bytes:
    try:
        with Image.open(BytesIO(content)) as uploaded_image:
            image = uploaded_image.convert("RGBA")
            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except UnidentifiedImageError as error: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid image") from error


def remove_existing_avatars(user_id: int) -> None:
    for extension in ALLOWED_AVATAR_EXTENSIONS:
        current_candidate = AVATARS_MEDIA_DIR / f"{user_id}{extension}"
        if current_candidate.exists(): current_candidate.unlink()


async def save_avatar(user_id: int, content: bytes) -> Path:
    target_path = build_avatar_path(user_id)
    async with aiofiles.open(target_path, "wb") as target_file: await target_file.write(content)
    return target_path
