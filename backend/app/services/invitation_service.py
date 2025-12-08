"""
User invitation and password reset service
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets
import hashlib
from pydantic import BaseModel, EmailStr
import redis.asyncio as redis

from app.config import settings


class InvitationToken(BaseModel):
    token: str
    email: str
    role: str
    created_by: int
    expires_at: datetime


class PasswordResetToken(BaseModel):
    token: str
    user_id: int
    email: str
    expires_at: datetime


class InvitationService:
    """Service for managing user invitations and password resets"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self.invitation_ttl = 7 * 24 * 60 * 60  # 7 days
        self.reset_ttl = 1 * 60 * 60  # 1 hour
    
    async def get_redis(self) -> redis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    @staticmethod
    def _generate_token() -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    # ============================================
    # USER INVITATIONS
    # ============================================
    
    async def create_invitation(
        self,
        email: str,
        role: str,
        created_by: int
    ) -> str:
        """Create a new user invitation"""
        r = await self.get_redis()
        
        token = self._generate_token()
        token_hash = self._hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.invitation_ttl)
        
        invitation_data = {
            "email": email,
            "role": role,
            "created_by": created_by,
            "expires_at": expires_at.isoformat()
        }
        
        # Store invitation
        import json
        await r.setex(
            f"invitation:{token_hash}",
            self.invitation_ttl,
            json.dumps(invitation_data)
        )
        
        # Also index by email for lookup
        await r.setex(
            f"invitation:email:{email}",
            self.invitation_ttl,
            token_hash
        )
        
        return token
    
    async def get_invitation(self, token: str) -> Optional[InvitationToken]:
        """Get invitation by token"""
        r = await self.get_redis()
        
        token_hash = self._hash_token(token)
        data = await r.get(f"invitation:{token_hash}")
        
        if not data:
            return None
        
        import json
        invitation_data = json.loads(data)
        
        return InvitationToken(
            token=token,
            email=invitation_data["email"],
            role=invitation_data["role"],
            created_by=invitation_data["created_by"],
            expires_at=datetime.fromisoformat(invitation_data["expires_at"])
        )
    
    async def consume_invitation(self, token: str) -> bool:
        """Mark invitation as used (delete it)"""
        r = await self.get_redis()
        
        token_hash = self._hash_token(token)
        
        # Get invitation data first to get email
        data = await r.get(f"invitation:{token_hash}")
        if data:
            import json
            invitation_data = json.loads(data)
            await r.delete(f"invitation:email:{invitation_data['email']}")
        
        result = await r.delete(f"invitation:{token_hash}")
        return result > 0
    
    async def cancel_invitation(self, email: str) -> bool:
        """Cancel pending invitation by email"""
        r = await self.get_redis()
        
        token_hash = await r.get(f"invitation:email:{email}")
        if token_hash:
            await r.delete(f"invitation:{token_hash}")
            await r.delete(f"invitation:email:{email}")
            return True
        return False
    
    # ============================================
    # PASSWORD RESET
    # ============================================
    
    async def create_reset_token(self, user_id: int, email: str) -> str:
        """Create a password reset token"""
        r = await self.get_redis()
        
        # Delete any existing reset token for this user
        existing_hash = await r.get(f"reset:user:{user_id}")
        if existing_hash:
            await r.delete(f"reset:{existing_hash}")
        
        token = self._generate_token()
        token_hash = self._hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.reset_ttl)
        
        reset_data = {
            "user_id": user_id,
            "email": email,
            "expires_at": expires_at.isoformat()
        }
        
        import json
        await r.setex(
            f"reset:{token_hash}",
            self.reset_ttl,
            json.dumps(reset_data)
        )
        
        # Index by user_id
        await r.setex(
            f"reset:user:{user_id}",
            self.reset_ttl,
            token_hash
        )
        
        return token
    
    async def get_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        """Get password reset token"""
        r = await self.get_redis()
        
        token_hash = self._hash_token(token)
        data = await r.get(f"reset:{token_hash}")
        
        if not data:
            return None
        
        import json
        reset_data = json.loads(data)
        
        return PasswordResetToken(
            token=token,
            user_id=reset_data["user_id"],
            email=reset_data["email"],
            expires_at=datetime.fromisoformat(reset_data["expires_at"])
        )
    
    async def consume_reset_token(self, token: str) -> bool:
        """Mark reset token as used"""
        r = await self.get_redis()
        
        token_hash = self._hash_token(token)
        
        # Get user_id first
        data = await r.get(f"reset:{token_hash}")
        if data:
            import json
            reset_data = json.loads(data)
            await r.delete(f"reset:user:{reset_data['user_id']}")
        
        result = await r.delete(f"reset:{token_hash}")
        return result > 0


# Global instance
invitation_service = InvitationService()
