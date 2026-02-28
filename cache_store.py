from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: datetime
    created_at: datetime


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
        self._expirations = 0

    def get(self, key: str) -> Any | None:
        value, _, _ = self.get_with_meta(key)
        return value

    def get_with_meta(self, key: str) -> tuple[Any | None, bool, datetime | None]:
        now = datetime.now(UTC)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None, False, None
            if entry.expires_at <= now:
                self._store.pop(key, None)
                self._expirations += 1
                self._misses += 1
                return None, False, None
            self._hits += 1
            return entry.value, True, entry.created_at

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        created_at = datetime.now(UTC)
        expires_at = created_at + timedelta(seconds=ttl_seconds)
        with self._lock:
            self._store[key] = _CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=created_at,
            )

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict[str, float | int]:
        with self._lock:
            requests = self._hits + self._misses
            hit_ratio = (self._hits / requests) if requests else 0.0
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "expirations": self._expirations,
                "hit_ratio": round(hit_ratio, 3),
            }


http_json_cache = TTLCache()
