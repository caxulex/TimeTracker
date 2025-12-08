"""
User invitations and password reset router
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.database import get_db
from app.models import User
from app.dependencies import get_current_active_user, get_current_admin_user
from app.services.invitation_service import invitation_service
from app.services.auth_service import auth_service
from app.schemas.auth import Message

router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="regular_user", pattern="^(super_admin|regular_user)$")


class InvitationResponse(BaseModel):
    email: str
    role: str
    token: str
    invite_url: str
    expires_at: datetime


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class AcceptInvitationRequest(BaseModel):
    token: str
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)


# ============================================
# INVITATION ENDPOINTS (Admin only)
# ============================================

@router.post("/invite", response_model=InvitationResponse)
async def create_invitation(
    invitation: InvitationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a user invitation (admin only)"""
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == invitation.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create invitation token
    token = await invitation_service.create_invitation(
        email=invitation.email,
        role=invitation.role,
        created_by=current_user.id
    )
    
    # Build invite URL
    base_url = str(request.base_url).rstrip("/")
    invite_url = f"{base_url.replace(':8080', ':5173')}/accept-invite?token={token}"
    
    # Get invitation details
    inv = await invitation_service.get_invitation(token)
    
    return InvitationResponse(
        email=invitation.email,
        role=invitation.role,
        token=token,
        invite_url=invite_url,
        expires_at=inv.expires_at
    )


@router.delete("/invite/{email}", response_model=Message)
async def cancel_invitation(
    email: str,
    current_user: User = Depends(get_current_admin_user)
):
    """Cancel a pending invitation (admin only)"""
    success = await invitation_service.cancel_invitation(email)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending invitation found for this email"
        )
    
    return Message(message="Invitation cancelled successfully")


@router.post("/accept-invite")
async def accept_invitation(
    data: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Accept an invitation and create account"""
    # Validate invitation
    invitation = await invitation_service.get_invitation(data.token)
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation token"
        )
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == invitation.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create user
    hashed_password = auth_service.hash_password(data.password)
    new_user = User(
        email=invitation.email,
        name=data.name,
        hashed_password=hashed_password,
        role=invitation.role,
        is_active=True
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Consume the invitation
    await invitation_service.consume_invitation(data.token)
    
    # Generate tokens for the new user
    tokens = auth_service.create_tokens(new_user.id, new_user.email)
    
    return {
        "message": "Account created successfully",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role
        },
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer"
    }


# ============================================
# PASSWORD RESET ENDPOINTS
# ============================================

@router.post("/forgot-password", response_model=Message)
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request a password reset"""
    # Find user by email
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    # Always return success to prevent email enumeration
    if not user:
        return Message(message="If the email exists, a reset link has been sent")
    
    # Create reset token
    token = await invitation_service.create_reset_token(user.id, user.email)
    
    # In a real app, send email here
    # For now, we log the token (remove in production)
    import logging
    logging.info(f"Password reset token for {user.email}: {token}")
    
    return Message(message="If the email exists, a reset link has been sent")


@router.post("/reset-password", response_model=Message)
async def reset_password(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    # Validate token
    reset_token = await invitation_service.get_reset_token(data.token)
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.hashed_password = auth_service.hash_password(data.new_password)
    await db.commit()
    
    # Consume the reset token
    await invitation_service.consume_reset_token(data.token)
    
    return Message(message="Password reset successfully")


@router.get("/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """Verify if a reset token is valid"""
    reset_token = await invitation_service.get_reset_token(token)
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {"valid": True, "email": reset_token.email}


@router.get("/verify-invite-token/{token}")
async def verify_invite_token(token: str):
    """Verify if an invitation token is valid"""
    invitation = await invitation_service.get_invitation(token)
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation token"
        )
    
    return {"valid": True, "email": invitation.email, "role": invitation.role}
