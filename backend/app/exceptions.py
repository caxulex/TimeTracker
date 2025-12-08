"""
Custom Exception Classes
SEC-010: Sanitized Error Responses Implementation
Provides safe error messages without exposing internals
"""

from fastapi import HTTPException, status
from typing import Optional, Any, Dict
import uuid
import logging

logger = logging.getLogger(__name__)


class AppException(HTTPException):
    """
    Base application exception with safe error messages.
    Internal details are logged but not exposed to clients.
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        internal_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.request_id = str(uuid.uuid4())[:8]
        self.internal_message = internal_message
        self.details = details or {}
        
        # Log internal details
        if internal_message:
            logger.error(f"[{self.request_id}] {code}: {internal_message}")
        
        super().__init__(
            status_code=status_code,
            detail={
                "error": code,
                "message": message,
                "request_id": self.request_id
            }
        )


class AuthenticationError(AppException):
    """Authentication failed"""
    def __init__(
        self,
        message: str = "Authentication failed",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="authentication_error",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            internal_message=internal_message
        )


class AuthorizationError(AppException):
    """Authorization failed - insufficient permissions"""
    def __init__(
        self,
        message: str = "Insufficient permissions",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="authorization_error",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            internal_message=internal_message
        )


class NotFoundError(AppException):
    """Resource not found"""
    def __init__(
        self,
        resource: str = "Resource",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="not_found",
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            internal_message=internal_message
        )


class ValidationError(AppException):
    """Validation error"""
    def __init__(
        self,
        message: str = "Validation error",
        details: Optional[Dict[str, Any]] = None,
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="validation_error",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            internal_message=internal_message,
            details=details
        )


class ConflictError(AppException):
    """Resource conflict (e.g., duplicate)"""
    def __init__(
        self,
        message: str = "Resource already exists",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="conflict",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            internal_message=internal_message
        )


class RateLimitError(AppException):
    """Rate limit exceeded"""
    def __init__(
        self,
        retry_after: int = 60,
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="rate_limit_exceeded",
            message="Too many requests. Please try again later.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            internal_message=internal_message,
            details={"retry_after": retry_after}
        )


class AccountLockedError(AppException):
    """Account is locked due to too many failed attempts"""
    def __init__(
        self,
        lockout_remaining: int,
        internal_message: Optional[str] = None
    ):
        minutes = lockout_remaining // 60
        super().__init__(
            code="account_locked",
            message=f"Account is temporarily locked. Please try again in {minutes} minutes.",
            status_code=status.HTTP_423_LOCKED,
            internal_message=internal_message,
            details={"lockout_remaining_seconds": lockout_remaining}
        )


class PasswordValidationError(AppException):
    """Password doesn't meet requirements"""
    def __init__(
        self,
        errors: list,
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="password_validation_error",
            message="Password does not meet security requirements",
            status_code=status.HTTP_400_BAD_REQUEST,
            internal_message=internal_message,
            details={"requirements": errors}
        )


class TokenError(AppException):
    """Token-related error"""
    def __init__(
        self,
        message: str = "Invalid or expired token",
        internal_message: Optional[str] = None
    ):
        super().__init__(
            code="token_error",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            internal_message=internal_message
        )


class InternalError(AppException):
    """Internal server error - hides technical details"""
    def __init__(
        self,
        internal_message: str
    ):
        super().__init__(
            code="internal_error",
            message="An internal error occurred. Please try again later.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            internal_message=internal_message
        )
