from typing import Any
from dataclasses import dataclass

@dataclass(frozen=True)
class BitrixSyncBatchResult:
    snapshots: dict[int, dict[str, Any]]
    errors: dict[int, str]