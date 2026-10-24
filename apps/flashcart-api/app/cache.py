"""Small in-process TTL cache for hot read paths (caching strategies #6, cache invalidation #7).

Cache-aside: read → miss → load from MongoDB → store. Admin writes call invalidate_prefix() on the
instance that handled the write; other instances converge within the TTL (bounded staleness, which is
acceptable for catalog browsing but never used for stock checks or prices at checkout).
"""

import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int = 512) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None or item[0] < time.monotonic():
            self._data.pop(key, None)
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return item[1]

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    def invalidate_prefix(self, prefix: str) -> None:
        for key in [k for k in self._data if k.startswith(prefix)]:
            del self._data[key]

    def clear(self) -> None:
        self._data.clear()


catalog_cache = TTLCache(ttl_seconds=30)
