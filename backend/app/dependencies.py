"""
Authentication dependencies for FastAPI
SEC-002: Token blacklist checking integrated
SEC-013: Enhanced WebSocket authentication
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.services.auth_service import auth_service
from app.services.token_blacklist import token_blacklist

security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from the JWT token
    SEC-002: Check token blacklist
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = auth_service.decode_token(token)

    if payload is None:
        raise credentials_exception

    # Check token type
    if payload.get("type") != "access":
        raise credentials_exception

    # SEC-002: Check if token is blacklisted
    jti = payload.get("jti")
    if jti:
        try:
            if await token_blacklist.is_blacklisted(jti):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception:
            # If Redis is unavailable, continue (fail open for availability)
            # In high-security environments, you might want to fail closed
            pass

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify they are an admin"""
    if current_user.role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_role(allowed_roles: list[str]):
    """Dependency factory for role-based access control"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


async def get_current_user_ws(token: str) -> Optional[User]:
    """
    SEC-013: Get current user from JWT token for WebSocket connections.
    Enhanced with token blacklist checking.
    Returns None if authentication fails instead of raising exception.
    """
    from app.database import async_session_maker

    payload = auth_service.decode_token(token)
    if payload is None:
        return None

    if payload.get("type") != "access":
        return None

    # SEC-002: Check if token is blacklisted
    jti = payload.get("jti")
    if jti:
        try:
            if await token_blacklist.is_blacklisted(jti):
                return None
        except Exception:
            pass  # Fail open for WebSocket connections

    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            return None

        return user


# Aliases for common admin checks
require_admin = get_current_admin_user
