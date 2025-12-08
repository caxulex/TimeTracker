"""
Session management for tracking active user sessions
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List
import json
import hashlib
from pydantic import BaseModel
import redis.asyncio as redis

from app.config import settings


class SessionInfo(BaseModel):
    session_id: str
    user_id: int
    created_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    is_current: bool = False


class SessionManager:
    """Manage user sessions using Redis"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self.session_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 * 4  # 4x token lifetime
    
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
    def _generate_session_id(user_id: int, ip_address: str, user_agent: str) -> str:
        """Generate unique session ID"""
        data = f"{user_id}:{ip_address}:{user_agent}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]
    
    def _get_user_sessions_key(self, user_id: int) -> str:
        """Get Redis key for user sessions"""
        return f"sessions:user:{user_id}"
    
    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session data"""
        return f"sessions:data:{session_id}"
    
    async def create_session(
        self,
        user_id: int,
        ip_address: str,
        user_agent: str
    ) -> str:
        """Create a new session"""
        r = await self.get_redis()
        
        session_id = self._generate_session_id(user_id, ip_address, user_agent)
        now = datetime.now(timezone.utc)
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent[:256] if user_agent else "Unknown"
        }
        
        # Store session data
        await r.setex(
            self._get_session_key(session_id),
            self.session_ttl,
            json.dumps(session_data)
        )
        
        # Add to user's session list
        await r.sadd(self._get_user_sessions_key(user_id), session_id)
        await r.expire(self._get_user_sessions_key(user_id), self.session_ttl)
        
        return session_id
    
    async def update_activity(self, session_id: str) -> bool:
        """Update last activity time"""
        r = await self.get_redis()
        
        session_key = self._get_session_key(session_id)
        data = await r.get(session_key)
        
        if not data:
            return False
        
        session_data = json.loads(data)
        session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
        
        await r.setex(session_key, self.session_ttl, json.dumps(session_data))
        return True
    
    async def get_user_sessions(self, user_id: int, current_session_id: Optional[str] = None) -> List[SessionInfo]:
        """Get all active sessions for a user"""
        r = await self.get_redis()
        
        session_ids = await r.smembers(self._get_user_sessions_key(user_id))
        sessions = []
        
        for sid in session_ids:
            data = await r.get(self._get_session_key(sid))
            if data:
                session_data = json.loads(data)
                sessions.append(SessionInfo(
                    session_id=sid,
                    user_id=session_data["user_id"],
                    created_at=datetime.fromisoformat(session_data["created_at"]),
                    last_activity=datetime.fromisoformat(session_data["last_activity"]),
                    ip_address=session_data["ip_address"],
                    user_agent=session_data["user_agent"],
                    is_current=sid == current_session_id
                ))
            else:
                # Session expired, remove from set
                await r.srem(self._get_user_sessions_key(user_id), sid)
        
        # Sort by last activity
        sessions.sort(key=lambda x: x.last_activity, reverse=True)
        return sessions
    
    async def revoke_session(self, user_id: int, session_id: str) -> bool:
        """Revoke a specific session"""
        r = await self.get_redis()
        
        # Remove session data
        await r.delete(self._get_session_key(session_id))
        
        # Remove from user's session list
        await r.srem(self._get_user_sessions_key(user_id), session_id)
        
        return True
    
    async def revoke_all_sessions(self, user_id: int, except_session_id: Optional[str] = None) -> int:
        """Revoke all sessions for a user, optionally except current"""
        r = await self.get_redis()
        
        session_ids = await r.smembers(self._get_user_sessions_key(user_id))
        revoked = 0
        
        for sid in session_ids:
            if sid != except_session_id:
                await r.delete(self._get_session_key(sid))
                await r.srem(self._get_user_sessions_key(user_id), sid)
                revoked += 1
        
        return revoked
    
    async def is_session_valid(self, session_id: str) -> bool:
        """Check if session exists and is valid"""
        r = await self.get_redis()
        return await r.exists(self._get_session_key(session_id)) > 0


# Global instance
session_manager = SessionManager()
