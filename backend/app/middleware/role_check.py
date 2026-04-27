"""
Role Check Middleware
TASK-016: Add role check middleware for admin routes

B11 (Prompt 3): The previous in-module ``require_role`` and ``require_admin``
were divergent from the canonical implementations in ``app.dependencies``
(super_admin-only vs super_admin|admin|company_admin). To eliminate the
drift while preserving the ``from app.middleware import require_admin``
import path that has historically existed, this module now re-exports
the canonical helpers from ``app.dependencies``. ``RoleChecker`` /
``AdminOnly`` / ``AnyUser`` are retained for any class-based callers.
"""

from typing import List
from fastapi import Depends, HTTPException, status

from app.models import User
from app.dependencies import (
    get_current_active_user,
    require_admin,  # canonical: super_admin | admin | company_admin
    require_role,   # canonical: list[str] arg
)

__all__ = [
    "require_admin",
    "require_role",
    "require_any_user",
    "RoleChecker",
    "AdminOnly",
    "AnyUser",
]


def require_any_user():
    """Dependency that allows any authenticated user.

    Thin wrapper retained for backwards compatibility. Uses the canonical
    ``require_role`` from ``app.dependencies``.
    """
    return require_role(["super_admin", "admin", "company_admin", "regular_user"])


class RoleChecker:
    """
    Class-based role checker for more complex scenarios.

    Usage:
        role_checker = RoleChecker(["super_admin", "team_admin"])

        @router.get("/endpoint")
        async def endpoint(user: User = Depends(role_checker)):
            pass
    """

    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "message": "You don't have permission to perform this action",
                    "required_roles": self.allowed_roles,
                    "your_role": user.role
                }
            )
        return user


# Pre-configured role checkers
AdminOnly = RoleChecker(["super_admin"])
AnyUser = RoleChecker(["super_admin", "regular_user"])
