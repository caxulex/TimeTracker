"""
Authentication dependencies for FastAPI
SEC-002: Token blacklist checking integrated
SEC-013: Enhanced WebSocket authentication
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services.auth_service import auth_service
from app.services.token_blacklist import token_blacklist

logger = logging.getLogger(__name__)

security = HTTPBearer()


class BlacklistUnavailableError(Exception):
    """B4: Raised when the JWT blacklist backend (Redis) is unreachable.

    The auth path treats blacklist availability as a hard dependency —
    when we can't verify whether a token has been revoked, we refuse
    the request (fail-closed). Callers translate this into the
    appropriate transport-level error (HTTP 401 or WS 1011).
    """


async def _check_blacklist_or_fail_closed(jti: str) -> bool:
    """B4: Check the JWT blacklist with fail-closed semantics.

    Returns True if the JTI is blacklisted, False otherwise.
    Raises ``BlacklistUnavailableError`` on any backend failure
    (connection error, timeout, etc.). Callers MUST translate this
    exception into a transport-level rejection — never let it
    propagate as an unauthenticated success.
    """
    try:
        redis_client = await token_blacklist.get_redis()
        key = f"{token_blacklist._prefix}{jti}"
        return bool(await redis_client.exists(key))
    except Exception as exc:
        logger.error(
            "auth.blacklist_unavailable: %s: %s",
            type(exc).__name__,
            exc,
        )
        raise BlacklistUnavailableError(str(exc)) from exc


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

    # SEC-002 / B4: Check token blacklist (fail-closed on Redis outage).
    jti = payload.get("jti")
    if jti:
        try:
            is_blacklisted = await _check_blacklist_or_fail_closed(jti)
        except BlacklistUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication service temporarily unavailable",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

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
    """Get current user and verify they are an admin (includes company_admin)"""
    if current_user.role not in ["super_admin", "admin", "company_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


async def get_company_timezone(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Resolve the IANA timezone string for ``current_user``'s company.

    B6/B7: All day/week/month boundary computations across reports,
    work_sessions, and time_entries should be tenant-local. Falls back
    to ``"UTC"`` when:
      - The user has no ``company_id`` (platform super_admin).
      - The company row has a NULL/empty timezone (defensive — schema
        defaults to ``"UTC"``).

    This is async-safe: the relationship ``User.company`` uses default
    lazy loading which doesn't work in async contexts; we issue an
    explicit scalar query instead.
    """
    if current_user.company_id is None:
        return "UTC"
    # Lazy import to avoid a circular dependency between dependencies.py and
    # models/__init__.py at startup.
    from app.models import Company

    result = await db.execute(
        select(Company.timezone).where(Company.id == current_user.company_id)
    )
    tz = result.scalar_one_or_none()
    return tz or "UTC"


def require_role(allowed_roles: list[str]):
    """Dependency factory for role-based access control.

    Note: company_admin is treated as equivalent to admin for permission checks.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role
        # Treat company_admin as equivalent to admin for permission purposes
        effective_role = 'admin' if user_role == 'company_admin' else user_role

        # Check both the actual role and effective role
        if user_role not in allowed_roles and effective_role not in allowed_roles:
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
    from app.database import async_session

    payload = auth_service.decode_token(token)
    if payload is None:
        return None

    if payload.get("type") != "access":
        return None

    # SEC-002 / B4: Check token blacklist (fail-closed on Redis outage).
    # The WebSocket caller is responsible for closing the socket with
    # code 1011 when this raises ``BlacklistUnavailableError``.
    jti = payload.get("jti")
    if jti:
        if await _check_blacklist_or_fail_closed(jti):
            return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            return None

        return user


# Aliases for common admin checks
require_admin = get_current_admin_user

# Sentinel value to indicate "filter by NULL company_id"
FILTER_NULL_COMPANY = "FILTER_NULL"


def get_company_filter(user: User):
    """
    Get company filter for multi-tenant data isolation.

    ALL users are scoped to their company for strict data isolation:
    - Users with company_id see only their company's data
    - Users with NULL company_id see only NULL company_id data (platform users)

    This ensures white-label companies NEVER see each other's data,
    regardless of user role.

    Returns:
        - company_id (int) for company-scoped users
        - FILTER_NULL_COMPANY sentinel for platform users without a company
    """
    # Users with a company are scoped to their company
    if user.company_id is not None:
        return user.company_id

    # Platform users (no company) see only NULL company data
    return FILTER_NULL_COMPANY


def apply_company_filter(query, company_column, company_id):
    """
    Apply company filter to a query.
    Handles the NULL company_id case correctly.

    Args:
        query: SQLAlchemy query to filter
        company_column: The column to filter on (e.g., Team.company_id)
        company_id: The company_id from get_company_filter()

    Returns:
        Filtered query
    """
    if company_id is None:
        # Super admin - no filter, see everything
        return query
    elif company_id == FILTER_NULL_COMPANY:
        # Platform user without company - filter by NULL
        return query.where(company_column.is_(None))
    else:
        # Company-scoped user - filter by company_id
        return query.where(company_column == company_id)


def is_platform_admin(user: User) -> bool:
    """Check if user is a platform-level super admin (not company-bound)"""
    return user.company_id is None and user.role == 'super_admin'


def is_admin_user(user: User) -> bool:
    """
    Check if user has admin privileges.
    Includes: super_admin, admin, company_admin
    """
    return user.role in ["super_admin", "admin", "company_admin"]
