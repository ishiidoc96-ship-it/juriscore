import os
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

try:
    from jose import jwt
except ImportError:
    import jwt

from api.backend.models.database import async_session, User
from api.backend.models.schemas import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthResponse,
    AuthUserResponse,
    AccessRequest,
)

logger = logging.getLogger("juriscore")
router = APIRouter()

# Get JWT secret from environment, with a default only for development
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    # Only allow missing secret in development
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("JWT_SECRET environment variable is required in production")
    logger.warning("JWT_SECRET not set, using development default")
    SECRET_KEY = "juriscore-dev-secret-change-in-production"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt, pw_hash


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    _, computed = hash_password(password, salt)
    return computed == stored_hash


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_session():
    async with async_session() as session:
        yield session


async def get_current_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthLoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.password_hash or not user.salt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(request.password, user.salt, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_token(user.id)
    return AuthResponse(
        token=token,
        user=AuthUserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            university=user.university,
        ),
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(request: AuthSignupRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    salt, pw_hash = hash_password(request.password)
    user = User(
        name=request.name,
        email=request.email,
        university=request.university,
        password_hash=pw_hash,
        salt=salt,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    token = create_token(user.id)
    return AuthResponse(
        token=token,
        user=AuthUserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            university=user.university,
        ),
    )


@router.get("/me", response_model=AuthUserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return AuthUserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        university=current_user.university,
    )


@router.post("/request-access")
async def request_access(request: AccessRequest):
    logger.info(
        f"Access request: {request.name} ({request.email}) from {request.organization}"
    )
    return {
        "status": "success",
        "message": "Your access request has been received. We will review it and get back to you shortly.",
    }
