import threading, time, logging
from typing import Any, Callable
from collections import OrderedDict

logger = logging.getLogger(__name__)

class CacheEntry:
    __slots__ = ("value", "expires_at", "created_at")
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl if ttl > 0 else float("inf")
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class CacheService:
    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float = None):
        if ttl is None:
            ttl = self._default_ttl
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = CacheEntry(value, ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        with self._lock:
            self._cache.clear()

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: float = None) -> Any:
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl)
        return value

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "default_ttl": self._default_ttl,
            }

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._cache.keys())
