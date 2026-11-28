import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from time import monotonic
from typing import Any, TypeVar
from weakref import WeakValueDictionary

T = TypeVar("T")


class ReferenceCache:
    """Successful reads of stable directories only, owned by one credentialed client."""

    TTL_SECONDS = 60 * 60
    MAX_ENTRIES = 128

    def __init__(self) -> None:
        self._entries: dict[tuple, tuple[float, Any]] = {}
        # Active readers/waiters keep the lock alive; finished keys need no lock.
        self._locks: WeakValueDictionary[tuple, asyncio.Lock] = WeakValueDictionary()

    async def read(self, key: tuple, load: Callable[[], Awaitable[T]], *,
                   cacheable: Callable[[T], bool] = bool) -> T:
        lock = self._locks.get(key)
        if lock is None:
            self._locks[key] = lock = asyncio.Lock()
        async with lock:
            entry = self._entries.get(key)
            if entry is not None and monotonic() < entry[0]:
                return deepcopy(entry[1])
            self._entries.pop(key, None)
            value = await load()
            if cacheable(value):
                if len(self._entries) >= self.MAX_ENTRIES:
                    del self._entries[next(iter(self._entries))]
                self._entries[key] = (monotonic() + self.TTL_SECONDS, deepcopy(value))
            return value


def reference_rows(data: Any, field: str = "rows") -> list[dict[str, Any]]:
    rows = data.get(field) if isinstance(data, dict) and "errors" not in data else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) and row and "errors" not in row for row in rows):
        raise ValueError(f"Invalid MoySklad reference response: expected {field}")
    return rows
