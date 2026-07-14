from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import os
import logging

logger = logging.getLogger("juriscore")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

security = HTTPBearer(auto_error=False)


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/", "/docs", "/openapi.json"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        request.state.user = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{SUPABASE_URL}/auth/v1/user",
                        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        request.state.user = resp.json()
            except Exception as e:
                logger.warning(f"Auth middleware error: {e}")
        response = await call_next(request)
        return response
