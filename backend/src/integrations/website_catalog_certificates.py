from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import aiofiles
import httpx

from config import (
    MEDIA_DIR,
    PRODUCT_CERTIFICATES_MEDIA_DIR,
    PUBLIC_API_BASE_URL,
)


MAX_CERTIFICATE_SIZE_BYTES = 100 * 1024 * 1024
_SAFE_EXTENSION = re.compile(r"^\.[a-z0-9]{1,10}$")
_CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_PUBLIC_PATH_PREFIX = "/media/product-certificates/"


@dataclass(frozen=True)
class MirroredCertificate:
    path: Path
    url: str
    size_bytes: int
    content_type: str | None
    downloaded: bool


def _certificate_extension(
    *,
    original_name: str | None,
    source_url: str,
    content_type: str | None,
) -> str:
    candidates = (
        Path(original_name or "").suffix.casefold(),
        Path(unquote(urlsplit(source_url).path)).suffix.casefold(),
        _CONTENT_TYPE_EXTENSIONS.get((content_type or "").split(";", 1)[0].strip().casefold(), ""),
    )
    return next(
        (candidate for candidate in candidates if _SAFE_EXTENSION.fullmatch(candidate)),
        ".bin",
    )


def certificate_media_path(
    *,
    product_id: int,
    source_file_id: int,
    original_name: str | None,
    source_url: str,
    content_type: str | None,
) -> Path:
    extension = _certificate_extension(
        original_name=original_name,
        source_url=source_url,
        content_type=content_type,
    )
    return PRODUCT_CERTIFICATES_MEDIA_DIR / str(product_id) / f"{source_file_id}{extension}"


def certificate_public_url(path: Path) -> str:
    public_base_url = (PUBLIC_API_BASE_URL or "").strip().rstrip("/")
    parsed_base_url = urlsplit(public_base_url)
    if (
        parsed_base_url.scheme != "https"
        or parsed_base_url.hostname is None
        or parsed_base_url.username is not None
        or parsed_base_url.password is not None
        or parsed_base_url.path not in ("", "/")
        or parsed_base_url.query
        or parsed_base_url.fragment
    ):
        raise RuntimeError(
            "PUBLIC_API_BASE_URL must be an HTTPS origin for locally mirrored certificates"
        )
    try:
        relative_path = path.relative_to(MEDIA_DIR).as_posix()
    except ValueError as error:
        raise RuntimeError("Certificate file is outside the application media directory") from error
    version = path.stat().st_mtime_ns
    return f"{public_base_url}/media/{relative_path}?v={version}"


def certificate_local_path_from_url(url: str | None) -> Path | None:
    if not url:
        return None
    parsed_url = urlsplit(url)
    if not parsed_url.path.startswith(_PUBLIC_PATH_PREFIX):
        return None
    relative_path = unquote(parsed_url.path.removeprefix("/media/"))
    if not relative_path or ".." in Path(relative_path).parts:
        return None
    candidate = MEDIA_DIR / relative_path
    try:
        candidate.relative_to(PRODUCT_CERTIFICATES_MEDIA_DIR)
    except ValueError:
        return None
    return candidate


async def mirror_certificate(
    client: httpx.AsyncClient,
    *,
    product_id: int,
    source_file_id: int,
    source_url: str,
    original_name: str | None,
    content_type: str | None,
    expected_size_bytes: int,
) -> MirroredCertificate:
    parsed_source_url = urlsplit(source_url)
    if (
        parsed_source_url.scheme != "https"
        or parsed_source_url.hostname is None
        or parsed_source_url.username is not None
        or parsed_source_url.password is not None
    ):
        raise RuntimeError("Certificate source URL must use HTTPS without credentials")

    target_path = certificate_media_path(
        product_id=product_id,
        source_file_id=source_file_id,
        original_name=original_name,
        source_url=source_url,
        content_type=content_type,
    )
    if target_path.is_file():
        current_size = target_path.stat().st_size
        if current_size > 0 and (
            expected_size_bytes == 0 or current_size == expected_size_bytes
        ):
            return MirroredCertificate(
                path=target_path,
                url=certificate_public_url(target_path),
                size_bytes=current_size,
                content_type=content_type,
                downloaded=False,
            )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(f".{target_path.name}.{uuid4().hex}.tmp")
    downloaded_size = 0
    response_content_type: str | None = None
    try:
        async with client.stream(
            "GET",
            source_url,
            headers={"Accept": "application/pdf,image/*,application/octet-stream"},
        ) as response:
            response.raise_for_status()
            raw_content_length = response.headers.get("Content-Length")
            if raw_content_length:
                try:
                    content_length = int(raw_content_length)
                except ValueError as error:
                    raise RuntimeError("Certificate response has an invalid Content-Length") from error
                if content_length <= 0 or content_length > MAX_CERTIFICATE_SIZE_BYTES:
                    raise RuntimeError("Certificate response size is outside the allowed range")

            response_content_type = (
                response.headers.get("Content-Type", "").split(";", 1)[0].strip() or None
            )
            async with aiofiles.open(temporary_path, "wb") as target:
                async for chunk in response.aiter_bytes():
                    downloaded_size += len(chunk)
                    if downloaded_size > MAX_CERTIFICATE_SIZE_BYTES:
                        raise RuntimeError("Certificate download exceeds the allowed size")
                    await target.write(chunk)

        if downloaded_size <= 0:
            raise RuntimeError("Certificate download returned an empty file")
        if expected_size_bytes > 0 and downloaded_size != expected_size_bytes:
            raise RuntimeError(
                "Downloaded certificate size does not match Bitrix metadata"
            )
        os.replace(temporary_path, target_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return MirroredCertificate(
        path=target_path,
        url=certificate_public_url(target_path),
        size_bytes=downloaded_size,
        content_type=content_type or response_content_type,
        downloaded=True,
    )


def remove_local_certificate(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.relative_to(PRODUCT_CERTIFICATES_MEDIA_DIR)
    except ValueError:
        return False
    existed = path.exists()
    path.unlink(missing_ok=True)
    parent = path.parent
    if parent != PRODUCT_CERTIFICATES_MEDIA_DIR:
        try:
            parent.rmdir()
        except OSError:
            pass
    return existed
