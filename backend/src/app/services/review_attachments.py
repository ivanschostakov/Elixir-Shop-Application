from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, Request
from starlette import status

from config import MEDIA_DIR, REVIEWS_MEDIA_DIR

ALLOWED_REVIEW_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_REVIEW_IMAGES_COUNT = 6
MAX_REVIEW_IMAGE_SIZE_BYTES = 8 * 1024 * 1024
MAX_REVIEW_TOTAL_SIZE_BYTES = 24 * 1024 * 1024

_MIME_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def build_review_attachment_dir(review_id: int) -> Path:
    directory = REVIEWS_MEDIA_DIR / str(review_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_review_attachment_url(request: Request, image_path: Path) -> str:
    base_url = str(request.base_url).rstrip("/")
    version = int(image_path.stat().st_mtime_ns) if image_path.exists() else 0

    try:
        relative_path = image_path.relative_to(MEDIA_DIR).as_posix()
    except ValueError:
        relative_path = f"reviews/{image_path.name}"
    return f"{base_url}/media/{relative_path}?v={version}"


def validate_review_attachments_count(attachments_count: int) -> None:
    if attachments_count > MAX_REVIEW_IMAGES_COUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can upload up to {MAX_REVIEW_IMAGES_COUNT} images per review",
        )


def validate_review_attachment(content: bytes, *, mime_type: str | None) -> str:
    normalized_mime_type = (mime_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_mime_type not in ALLOWED_REVIEW_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WEBP review images are supported",
        )

    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded review image is empty")

    if len(content) > MAX_REVIEW_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Each review image must be 8 MB or smaller",
        )

    return normalized_mime_type


def validate_review_attachments_total_size(total_size_bytes: int) -> None:
    if total_size_bytes > MAX_REVIEW_TOTAL_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Total review images size must be 24 MB or smaller",
        )


def build_review_attachment_filename(mime_type: str) -> str:
    return f"{uuid4().hex}{_MIME_EXTENSION.get(mime_type, '.jpg')}"


async def save_review_attachment_file(review_id: int, *, filename: str, content: bytes) -> Path:
    target_path = build_review_attachment_dir(review_id) / filename
    async with aiofiles.open(target_path, "wb") as target_file:
        await target_file.write(content)
    return target_path


def remove_review_attachment_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        return
