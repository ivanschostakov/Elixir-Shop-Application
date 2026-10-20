from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MirroredCertificate:
    path: Path
    url: str
    size_bytes: int
    content_type: str | None
    downloaded: bool
