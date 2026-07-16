"""Core configuration, rate limiting, and shared dependencies for Juriscore."""
from __future__ import annotations

import os
import time
import asyncio
from functools import wraps
from typing import Any, AsyncGenerator, Optional

from fastapi import Depends, Request, HTTPException, status
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import async_session


# ── Settings ─────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = ""

    # AI / NVIDIA (fast model)
    NVIDIA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    # Mistral (reasoning model)
    MISTRAL_API_KEY: str = ""
    AI_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    AI_MODEL: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    AI_FALLBACK_MODEL: str = "meta/llama-3.1-8b-instruct"
    AI_TIMEOUT_SECONDS: int = 60
    AI_CACHE_TTL_SECONDS: int = 3600

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Rate limiting (per minute)
    RATE_LIMIT_SEARCH_PER_MIN: int = 30
    RATE_LIMIT_AI_PER_MIN: int = 10

    # CORS
    CORS_ORIGINS: str = "*"


settings = Settings()

RATE_LIMIT_SEARCH_PER_MIN = settings.RATE_LIMIT_SEARCH_PER_MIN
RATE_LIMIT_AI_PER_MIN = settings.RATE_LIMIT_AI_PER_MIN


# ── Rate limiting ────────────────────────────────────────────────────────────

class _RateBucket:
    """Simple sliding-window rate limiter (per-process)."""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]

    async def check(self, key: str) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._hits.setdefault(key, [])
            self._prune(key, now)
            if len(self._hits[key]) >= self.limit:
                return False
            self._hits[key].append(now)
            return True


_buckets: dict[str, _RateBucket] = {}


def rate_limit_dep(limit: int, bucket: str = "default"):
    """FastAPI dependency that enforces a per-minute rate limit."""

    async def _dep(request: Request):
        if bucket not in _buckets:
            _buckets[bucket] = _RateBucket(limit)
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}"
        ok = await _buckets[bucket].check(key)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {bucket}. Try again later.",
            )

    return _dep


# ── Shared session dependency ────────────────────────────────────────────────

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
