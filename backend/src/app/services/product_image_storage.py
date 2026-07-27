from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette import status

from src.app.services.upload_limits import read_upload_file_limited

ALLOWED_PRODUCT_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_PRODUCT_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
MAX_PRODUCT_IMAGE_DIMENSION = 2400


async def prepare_product_image(upload: UploadFile) -> bytes:
    from PIL import ImageOps

    content_type = (upload.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in ALLOWED_PRODUCT_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG and WEBP product images are supported",
        )
    content = await read_upload_file_limited(
        upload,
        max_bytes=MAX_PRODUCT_IMAGE_SIZE_BYTES,
        label="Product image",
    )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded product image is empty",
        )
    try:
        with Image.open(BytesIO(content)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            if image.width < 64 or image.height < 64:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Product image must be at least 64×64 pixels",
                )
            image.thumbnail(
                (MAX_PRODUCT_IMAGE_DIMENSION, MAX_PRODUCT_IMAGE_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = BytesIO()
            converted.save(output, format="PNG", optimize=True)
            return output.getvalue()
    except HTTPException:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid image",
        ) from error


async def save_product_image(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        async with aiofiles.open(temporary_path, "wb") as target:
            await target.write(content)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
