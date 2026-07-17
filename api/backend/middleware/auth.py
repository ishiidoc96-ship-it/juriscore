from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import logging

from api.backend.routers.auth import get_current_user
from api.backend.models.database import User

logger = logging.getLogger("juriscore")


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that adds user to request.state if valid auth header present."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        public_paths = ("/health", "/ready", "/", "/docs", "/openapi.json", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json", "/metrics")
        if request.url.path in public_paths or request.url.path.startswith("/metrics") or request.url.path.startswith("/api/v1/chat"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        request.state.user = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # Use the existing get_current_user logic from auth router
                # We need to create a session and decode the token
                from api.backend.models.database import async_session
                from api.backend.routers.auth import decode_token
                from sqlalchemy import select

                payload = decode_token(token)
                user_id = payload.get("sub")

                if user_id:
                    async with async_session() as session:
                        result = await session.execute(select(User).where(User.id == user_id))
                        user = result.scalar_one_or_none()
                        if user and user.is_active:
                            request.state.user = user
            except Exception as e:
                logger.warning(f"Auth middleware error: {e}")

        response = await call_next(request)
        return response


# Dependency for protecting routes - returns current user or raises 401
async def require_auth(request: Request) -> User:
    """Dependency that requires authentication. Use with Depends(require_auth)."""
    if not hasattr(request.state, 'user') or request.state.user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user


# Optional auth - returns user if authenticated, None otherwise
async def optional_auth(request: Request) -> Optional[User]:
    """Dependency that returns user if authenticated, None otherwise."""
    if hasattr(request.state, 'user') and request.state.user is not None:
        return request.state.user
    return None
