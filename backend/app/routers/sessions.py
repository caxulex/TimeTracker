"""
Sessions management router - View and revoke active sessions
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models import User
from app.dependencies import get_current_active_user
from app.services.session_manager import session_manager, SessionInfo

router = APIRouter()


class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    last_activity: str
    ip_address: str
    user_agent: str
    is_current: bool


class SessionsListResponse(BaseModel):
    sessions: List[SessionResponse]
    count: int


class RevokeResponse(BaseModel):
    message: str
    revoked_count: int = 1


@router.get("", response_model=SessionsListResponse)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """List all active sessions for current user"""
    # Get current session ID from header or generate one
    current_session_id = request.headers.get("X-Session-ID")
    
    sessions = await session_manager.get_user_sessions(
        current_user.id, 
        current_session_id
    )
    
    return SessionsListResponse(
        sessions=[
            SessionResponse(
                session_id=s.session_id[:8] + "...",  # Truncate for security
                created_at=s.created_at.isoformat(),
                last_activity=s.last_activity.isoformat(),
                ip_address=s.ip_address,
                user_agent=s.user_agent[:100],
                is_current=s.is_current
            )
            for s in sessions
        ],
        count=len(sessions)
    )


@router.delete("/{session_id}", response_model=RevokeResponse)
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Revoke a specific session"""
    # Get full sessions to find matching one
    sessions = await session_manager.get_user_sessions(current_user.id)
    
    # Find session by truncated ID
    target_session = None
    for s in sessions:
        if s.session_id.startswith(session_id.replace("...", "")):
            target_session = s
            break
    
    if not target_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Don't allow revoking current session through this endpoint
    current_session_id = request.headers.get("X-Session-ID")
    if target_session.session_id == current_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke current session. Use logout instead."
        )
    
    await session_manager.revoke_session(current_user.id, target_session.session_id)
    
    return RevokeResponse(
        message="Session revoked successfully",
        revoked_count=1
    )


@router.delete("", response_model=RevokeResponse)
async def revoke_all_other_sessions(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Revoke all sessions except current"""
    current_session_id = request.headers.get("X-Session-ID")
    
    revoked = await session_manager.revoke_all_sessions(
        current_user.id,
        except_session_id=current_session_id
    )
    
    return RevokeResponse(
        message=f"Revoked {revoked} session(s)",
        revoked_count=revoked
    )
