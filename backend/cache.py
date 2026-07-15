"""
Cache layer for Juriscore.

Two tiers:
- MemoryCache   — process-local, fastest, unlimited scope.
  Use for per-request memoization, singleton data, and short-lived lookups.

- TTLCache      — process-local with time-based expiry.
  Use for query results (DB lookups, external API calls) that can tolerate
  bounded staleness.  Multi-worker deployments should move this to Redis.

Neither implementation is threaded-safe by design (they are read-mostly and
writes are atomic dict ops done from the event loop).  If threads are
introduced, wrap writes in a Lock.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger("juriscore.cache")

F = TypeVar("F", bound=Callable)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory unbounded cache (process-local singleton)
# ─────────────────────────────────────────────────────────────────────────────
class MemoryCache:
    """Simple dict-backed in-memory cache.  No eviction — use for singleton
    or near-singleton data (courts list, doc-type map, etc.)."""

    _instance: Optional[MemoryCache] = None
    _lock = threading.Lock()

    def __new__(cls) -> MemoryCache:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, Any] = {}
        return cls._instance

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# ─────────────────────────────────────────────────────────────────────────────
# TTL cache
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class _TTLRecord:
    value: Any
    expires_at: float  # monotonic seconds


class TTLCache:
    """Time-aware dict.  Every entry has an expiry and is evicted lazily on
    read or periodically on write.  Threading is handled via a reentrant lock."""

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        self._default_ttl = default_ttl_seconds
        self._store: dict[str, _TTLRecord] = {}
        self._lock = threading.RLock()

    def _expired(self, key: str) -> bool:
        rec = self._store.get(key)
        if rec is None:
            return True
        if time.monotonic() > rec.expires_at:
            del self._store[key]
            return True
        return False

    def get(self, key: str) -> Any:
        with self._lock:
            if self._expired(key):
                return None
            return self._store[key].value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        with self._lock:
            self._store[key] = _TTLRecord(
                value=value, expires_at=time.monotonic() + ttl
            )

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove every key starting with ``prefix``.  Returns count removed."""
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Named cache singletons (populate from core.settings if needed)
# ─────────────────────────────────────────────────────────────────────────────
response_cache = TTLCache(default_ttl_seconds=300)   # 5 minutes
query_cache   = TTLCache(default_ttl_seconds=60)     # 1 minute   — DB reads
scrape_cache  = TTLCache(default_ttl_seconds=300)    # 5 minutes  — external HTTP
ai_cache      = TTLCache(default_ttl_seconds=3600)   # 1 hour     — LLM calls


# ─────────────────────────────────────────────────────────────────────────────
# Key helpers
# ─────────────────────────────────────────────────────────────────────────────
def _stable_key(*parts: Any) -> str:
    """Deterministic hash for cache keys — avoids key-length limits."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Decorator: cache-aside for async functions
# ─────────────────────────────────────────────────────────────────────────────
def cached(
    cache: TTLCache = response_cache,
    ttl: Optional[float] = None,
    key_fn: Optional[Callable[..., str]] = None,
):
    """Cache the decorated async function's return value.

    Usage::

        @cached(cache=query_cache, ttl=60)
        async def fetch_user(user_id: str) -> dict:
            ...

        # Explicit key (when args aren't enough):
        @cached(cache=response_cache, key_fn=lambda q, f: f"search:{q}:{f}")
        async def search(q: str, filters: dict) -> dict:
            ...
    """

    def decorator(func: F) -> F:
        import functools

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if key_fn is not None:
                try:
                    key = key_fn(*args, **kwargs)
                except Exception:  # noqa: BLE001
                    key = _stable_key(func.__name__, args, kwargs)
            else:
                key = _stable_key(func.__name__, args, kwargs)

            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug("cache hit: %s", key)
                return cached_value

            result = await func(*args, **kwargs)
            cache.set(key, result, ttl_seconds=ttl)
            logger.debug("cache miss+set: %s", key)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
