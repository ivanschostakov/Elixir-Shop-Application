import base64
import binascii
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import aiofiles
import httpx
from fastapi import Request
from PIL import Image, UnidentifiedImageError

from config import MEDIA_DIR, ORDERS_MEDIA_DIR

QR_EXTENSION = ".png"


def build_order_payment_qr_path(user_id: int, order_id: int) -> Path:
    directory = ORDERS_MEDIA_DIR / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"qr-{order_id}{QR_EXTENSION}"


def find_order_payment_qr_path(user_id: int, order_id: int) -> Path | None:
    candidate = ORDERS_MEDIA_DIR / str(user_id) / f"qr-{order_id}{QR_EXTENSION}"
    return candidate if candidate.exists() else None


def build_order_payment_qr_url(request: Request, image_path: Path | None) -> str | None:
    if image_path is None: return None

    base_url = str(request.base_url).rstrip("/")
    version = int(image_path.stat().st_mtime_ns)
    try: relative_path = image_path.relative_to(MEDIA_DIR).as_posix()
    except ValueError: relative_path = f"orders/{image_path.name}"
    return f"{base_url}/media/{relative_path}?v={version}"


def _decode_data_url(value: str) -> bytes:
    _, encoded = value.split(",", 1)
    return base64.b64decode(encoded, validate=True)


def _decode_base64_blob(value: str) -> bytes:
    normalized = "".join(value.split())
    return base64.b64decode(normalized, validate=True)


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def _load_candidate_bytes(value: str) -> bytes:
    candidate = (value or "").strip()
    if not candidate: raise ValueError("QR source is empty")

    if candidate.startswith("data:") and ";base64," in candidate: return _decode_data_url(candidate)

    if _is_http_url(candidate):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client: response = await client.get(candidate)
        response.raise_for_status()
        return response.content

    return _decode_base64_blob(candidate)


def _convert_qr_to_png(content: bytes) -> bytes:
    with Image.open(BytesIO(content)) as qr_image:
        image = qr_image.convert("RGBA")
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


async def save_order_payment_qr(user_id: int, order_id: int, *, qr_image: str | None, qr_url: str | None) -> Path | None:
    errors: list[str] = []
    for source_name, source_value in (("qr_image", qr_image), ("qr_url", qr_url)):
        if not source_value:
            continue

        try:
            raw_content = await _load_candidate_bytes(source_value)
            png_content = _convert_qr_to_png(raw_content)
            target_path = build_order_payment_qr_path(user_id, order_id)
            if target_path.exists():
                async with aiofiles.open(target_path, "rb") as existing_file: existing_content = await existing_file.read()
                if existing_content == png_content: return target_path
            async with aiofiles.open(target_path, "wb") as target_file: await target_file.write(png_content)
            return target_path
        except (ValueError, binascii.Error, UnidentifiedImageError, httpx.HTTPError) as exc: errors.append(f"{source_name}: {exc}")

    if errors: raise RuntimeError("; ".join(errors))

    return find_order_payment_qr_path(user_id, order_id)
