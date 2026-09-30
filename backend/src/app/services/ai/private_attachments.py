"""Move legacy AI uploads out of static media without changing their IDs."""
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class PublicMediaFiles(StaticFiles):
    async def get_response(self, path, scope):
        # StaticFiles normalises the ASGI (decoded) path before this method.
        if path.replace("\\", "/").split("/", 1)[0].lower() == "attachments":
            return Response(status_code=404, headers={"Cache-Control": "no-store"})
        return await super().get_response(path, scope)


def migrate_legacy_ai_files(source: Path, destination: Path) -> int:
    """Idempotent; never overwrite a different file or follow a symlink."""
    if not source.exists():
        return 0
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("AI attachment storage must not be a symlink")
    destination.mkdir(parents=True, exist_ok=True)
    moved = 0
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_symlink() or target.is_symlink():
            raise ValueError("AI attachment storage contains a symlink")
        if entry.is_dir():
            moved += migrate_legacy_ai_files(entry, target)
            entry.rmdir()
        elif entry.is_file():
            if target.exists():
                with entry.open("rb") as left, target.open("rb") as right:
                    identical = hashlib.file_digest(left, "sha256").digest() == hashlib.file_digest(right, "sha256").digest()
                if not identical:
                    raise ValueError("Conflicting AI attachment files; refusing to overwrite")
                entry.unlink()
            else:
                # Media and private_media may be different Docker mounts. Copy
                # to a private temporary file, then publish atomically without
                # overwriting; an interrupted copy must never corrupt target.
                descriptor, temporary_name = tempfile.mkstemp(prefix=".ai-migration-", dir=destination)
                os.close(descriptor)
                temporary = Path(temporary_name)
                try:
                    shutil.copy2(entry, temporary)
                    os.link(temporary, target)
                    entry.unlink()
                finally:
                    temporary.unlink(missing_ok=True)
            moved += 1
    return moved
