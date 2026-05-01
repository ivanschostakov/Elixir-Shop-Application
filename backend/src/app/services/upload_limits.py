from fastapi import HTTPException, UploadFile
from starlette import status

UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


def format_upload_size_limit(max_bytes: int) -> str:
    mib = max_bytes / (1024 * 1024)
    if mib >= 1:
        return f"{mib:g} MB"
    return f"{max_bytes} bytes"


async def read_upload_file_limited(upload: UploadFile, *, max_bytes: int, label: str) -> bytes:
    content = bytearray()
    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        if len(content) + len(chunk) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"{label} exceeds {format_upload_size_limit(max_bytes)}",
            )
        content.extend(chunk)
    return bytes(content)
