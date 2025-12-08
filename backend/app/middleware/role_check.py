"""
Role Check Middleware
TASK-016: Add role check middleware for admin routes
Provides role-based access control decorators and dependencies
"""

from typing import List, Callable
from functools import wraps
from fastapi import Depends, HTTPException, status

from app.models import User
from app.dependencies import get_current_active_user


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role("super_admin"))):
            pass
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "message": "You don't have permission to perform this action",
                    "required_roles": list(allowed_roles),
                    "your_role": current_user.role
                }
            )
        return current_user
    return role_checker


def require_admin():
    """Dependency that requires super_admin role"""
    return require_role("super_admin")


def require_any_user():
    """Dependency that allows any authenticated user"""
    return require_role("super_admin", "regular_user")


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
