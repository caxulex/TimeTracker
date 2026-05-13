"""
Authentication router
SEC-002, SEC-003, SEC-004, SEC-011, SEC-015: Security Hardened
"""

import logging
from ipaddress import ip_address, ip_network
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    PasswordValidationError,
    ValidationError,
)
from app.models import User
from app.schemas.auth import (
    Message,
    PasswordChange,
    Token,
    TokenRefresh,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.audit_log import AuditEventType, audit_log
from app.services.auth_service import auth_service
from app.services.email_service import email_service
from app.services.login_security import login_security
from app.services.token_blacklist import token_blacklist
from app.utils.password_validator import validate_password_strength

logger = logging.getLogger(__name__)

router = APIRouter()


class LogoutRequest(BaseModel):
    """B15: Optional logout body so the client can send the refresh token
    for revocation alongside the access token. The field is optional so
    existing clients that POST /api/auth/logout with no body continue to
    work; in that case only the access token is blacklisted and a
    WARNING is logged.
    """
    refresh_token: Optional[str] = None


def _parse_trusted_proxy_networks():
    """Parse settings.TRUSTED_PROXIES into a list of ``ip_network`` objects.

    ``ip_network`` accepts both CIDR notation (``10.0.0.0/8``) and bare
    addresses (``10.0.0.5``); the latter become /32 (or /128) networks.
    Invalid entries are skipped with a WARNING — the deployment shouldn't
    crash because of a typo, but the operator must see it.
    """
    networks = []
    for raw in settings.TRUSTED_PROXIES:
        try:
            networks.append(ip_network(raw, strict=False))
        except ValueError:
            logger.warning(
                "auth.invalid_trusted_proxy: ignoring TRUSTED_PROXIES entry %r",
                raw,
            )
    return networks


def _is_trusted_proxy(peer_ip: str, networks) -> bool:
    """True if ``peer_ip`` parses and is contained in any trusted network."""
    if not networks:
        return False
    try:
        peer = ip_address(peer_ip)
    except ValueError:
        return False
    return any(peer in net for net in networks)


def get_client_ip(request: Request) -> str:
    """Extract client IP, honoring X-Forwarded-For only behind a trusted proxy.

    B16: previously XFF was honored unconditionally, which let any direct
    caller spoof the IP recorded in audit logs (and bypass any IP-keyed
    rate limiting). Now the immediate peer IP must be in
    ``settings.TRUSTED_PROXIES`` before XFF is consulted; otherwise we
    return the peer IP. When trusted, the leftmost non-trusted-proxy IP
    in XFF is returned (RFC 7239 semantics).
    """
    peer_ip = request.client.host if request.client else "unknown"
    trusted_networks = _parse_trusted_proxy_networks()

    if not _is_trusted_proxy(peer_ip, trusted_networks):
        return peer_ip

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        for raw_ip in forwarded.split(","):
            candidate = raw_ip.strip()
            if not candidate:
                continue
            if _is_trusted_proxy(candidate, trusted_networks):
                # Skip our own infrastructure; keep walking left-to-right
                # for the originating client.
                continue
            return candidate
        # All entries were trusted proxies — fall through to peer.
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return peer_ip


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    SEC-003: Strong password validation required
    """
    client_ip = get_client_ip(request)

    # SEC-003: Validate password strength
    is_valid, password_errors = validate_password_strength(user_data.password)
    if not is_valid:
        raise PasswordValidationError(errors=password_errors)

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise ConflictError(message="Email already registered")

    # Create new user
    hashed_password = auth_service.hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        role="regular_user",
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # SEC-015: Audit log
    await audit_log.log(
        event_type=AuditEventType.USER_CREATED,
        user_id=new_user.id,
        user_email=new_user.email,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent"),
        action="register"
    )

    # Send welcome email (non-blocking: SMTP failures must not fail registration)
    try:
        await email_service.send_welcome_email(
            to_email=new_user.email,
            user_name=new_user.name,
        )
    except Exception as exc:
        logger.error(
            "Failed to send welcome email to %s after registration: %s",
            new_user.email,
            exc,
        )

    return new_user


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Login and get access tokens
    SEC-011: Account lockout after failed attempts
    SEC-015: Audit logging
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    # SEC-011: Check if account is locked
    is_locked, lockout_remaining = await login_security.is_locked(user_data.email)
    if is_locked:
        await audit_log.log_auth_failure(
            email=user_data.email,
            ip_address=client_ip,
            reason="account_locked",
            user_agent=user_agent
        )
        raise AccountLockedError(lockout_remaining=lockout_remaining)

    # Find user by email
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(user_data.password, user.password_hash):
        # SEC-011: Record failed attempt
        attempts, is_now_locked = await login_security.record_failed_attempt(user_data.email)

        # SEC-015: Log failed login
        await audit_log.log_auth_failure(
            email=user_data.email,
            ip_address=client_ip,
            reason="invalid_credentials",
            user_agent=user_agent
        )

        if is_now_locked:
            await audit_log.log_account_locked(
                email=user_data.email,
                ip_address=client_ip,
                attempts=attempts
            )
            raise AccountLockedError(lockout_remaining=900)

        raise AuthenticationError(message="Incorrect email or password")

    if not user.is_active:
        await audit_log.log_auth_failure(
            email=user_data.email,
            ip_address=client_ip,
            reason="account_deactivated",
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    # SEC-011: Clear failed attempts on successful login
    await login_security.clear_attempts(user_data.email)

    # Create tokens
    tokens = auth_service.create_tokens(user.id, user.email)

    # SEC-015: Log successful login
    await audit_log.log_auth_success(
        user_id=user.id,
        user_email=user.email,
        ip_address=client_ip,
        user_agent=user_agent
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"]
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    SEC-002: Check token blacklist
    """
    client_ip = get_client_ip(request)

    payload = auth_service.decode_token(token_data.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise AuthenticationError(message="Invalid refresh token")

    # SEC-002: Check if token is blacklisted
    jti = payload.get("jti")
    if jti and await token_blacklist.is_blacklisted(jti):
        raise AuthenticationError(message="Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(message="Invalid refresh token")

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise AuthenticationError(message="User not found or inactive")

    # SEC-002: Blacklist old refresh token
    if jti:
        expiry = auth_service.get_token_expiry_seconds(token_data.refresh_token)
        await token_blacklist.blacklist_token(jti, expiry)

    # Create new tokens
    tokens = auth_service.create_tokens(user.id, user.email)

    # SEC-015: Log token refresh
    await audit_log.log(
        event_type=AuditEventType.TOKEN_REFRESH,
        user_id=user.id,
        user_email=user.email,
        ip_address=client_ip
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"]
    }


@router.post("/logout", response_model=Message)
async def logout(
    request: Request,
    body: Optional[LogoutRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
):
    """
    Logout and blacklist current token(s).
    SEC-002: Token blacklisting on logout.
    B15: Also blacklist the refresh token (when supplied) so it can no
    longer be exchanged for a fresh access token. Missing/invalid
    refresh tokens still produce a 200 (the access token is always
    blacklisted) but emit ``auth.logout_missing_refresh`` at WARNING
    level so operators can detect frontends that have not been updated.
    """
    client_ip = get_client_ip(request)

    # Blacklist the access token (existing behavior).
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        jti = auth_service.get_token_jti(token)

        if jti:
            expiry = auth_service.get_token_expiry_seconds(token)
            await token_blacklist.blacklist_token(jti, expiry)

    # B15: Blacklist the refresh token if provided and valid.
    refresh_token = body.refresh_token if body and body.refresh_token else None
    if refresh_token:
        refresh_payload = auth_service.decode_token(refresh_token)
        if (
            refresh_payload is not None
            and refresh_payload.get("type") == "refresh"
            and refresh_payload.get("jti")
        ):
            refresh_jti = refresh_payload["jti"]
            refresh_expiry = auth_service.get_token_expiry_seconds(refresh_token)
            await token_blacklist.blacklist_token(refresh_jti, refresh_expiry)
        else:
            logger.warning(
                "auth.logout_missing_refresh: user_id=%s reason=invalid_refresh_token",
                current_user.id,
            )
    else:
        logger.warning(
            "auth.logout_missing_refresh: user_id=%s reason=no_refresh_token_in_body",
            current_user.id,
        )

    # SEC-015: Log logout
    await audit_log.log_logout(
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=client_ip
    )

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user profile"""
    client_ip = get_client_ip(request)

    if user_data.email and user_data.email != current_user.email:
        # Check if new email is already taken
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise ConflictError(message="Email already in use")
        current_user.email = user_data.email

    if user_data.name:
        current_user.name = user_data.name

    await db.commit()
    await db.refresh(current_user)

    # SEC-015: Audit log
    await audit_log.log(
        event_type=AuditEventType.USER_UPDATED,
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=client_ip,
        action="profile_update"
    )

    return current_user


@router.put("/password", response_model=Message)
async def change_password(
    password_data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password
    SEC-003: Strong password validation
    SEC-002: Invalidate all existing tokens
    """
    client_ip = get_client_ip(request)

    # Verify current password
    if not auth_service.verify_password(password_data.current_password, current_user.password_hash):
        raise ValidationError(message="Current password is incorrect")

    # SEC-003: Validate new password strength
    is_valid, password_errors = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise PasswordValidationError(errors=password_errors)

    # Update password
    current_user.password_hash = auth_service.hash_password(password_data.new_password)
    await db.commit()

    # SEC-002: Invalidate all existing tokens for this user
    await token_blacklist.blacklist_user_tokens(current_user.id)

    # SEC-015: Audit log
    await audit_log.log(
        event_type=AuditEventType.PASSWORD_CHANGE,
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=client_ip
    )

    return {"message": "Password updated successfully. Please log in again."}
