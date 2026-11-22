"""Publish visually approved public photos through the application's media host."""
import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from config import API_BASE_URL, MEDIA_DIR, PUBLIC_API_BASE_URL

from .recipe_images import MAX_PHOTO_BYTES, recipe_photo_mime

_extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _publish(image, content):
    mime, raw = content
    if mime not in _extensions or not raw or len(raw) > MAX_PHOTO_BYTES or recipe_photo_mime(raw) != mime:
        raise ValueError("Invalid recipe photograph")
    base = (PUBLIC_API_BASE_URL or API_BASE_URL or "").rstrip("/")
    origin = urlsplit(base)
    if origin.scheme not in {"https", "http"} or not origin.netloc:
        raise ValueError("Public media URL is not configured")
    directory = Path(MEDIA_DIR) / "recipe-photos"
    directory.mkdir(parents=True, exist_ok=True)
    # The URL reveals only a hash of an already public photo, never recipe/profile data.
    filename = hashlib.sha256(raw).hexdigest() + _extensions[mime]
    target = directory / filename
    if not target.is_file() or target.read_bytes() != raw:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".recipe-", delete=False) as file:
                temporary = Path(file.name)
                file.write(raw)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return image.model_copy(update={"url": f"{base}/media/recipe-photos/{filename}"})


async def publish_recipe_photo(image, content):
    # Wikimedia rejects anonymous mobile image requests. Reuse the exact bytes
    # already inspected instead of sending the phone back to the remote host.
    return await asyncio.to_thread(_publish, image, content)
