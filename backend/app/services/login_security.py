"""
Login Security Service
SEC-011: Account Lockout Implementation
Tracks failed login attempts and implements account lockout
"""

import redis.asyncio as redis
from typing import Optional, Tuple
from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class LoginSecurityService:
    """
    Service for managing login security including:
    - Failed attempt tracking
    - Account lockout after threshold
    - Progressive delays
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._prefix = "login_security:"
        self._max_attempts = 5
        self._lockout_seconds = 900  # 15 minutes
        self._attempt_window = 300  # 5 minutes window for counting attempts
    
    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
            except Exception as e:
                logger.error(f"Failed to connect to Redis for login security: {e}")
                raise
        return self._redis
    
    async def record_failed_attempt(self, identifier: str) -> Tuple[int, bool]:
        """
        Record a failed login attempt.
        
        Args:
            identifier: Email or IP address to track
        
        Returns:
            Tuple of (current_attempts, is_now_locked)
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}attempts:{identifier}"
            
            # Increment attempt counter
            attempts = await redis_client.incr(key)
            
            # Set expiry on first attempt
            if attempts == 1:
                await redis_client.expire(key, self._attempt_window)
            
            # Check if should lock
            is_locked = attempts >= self._max_attempts
            
            if is_locked:
                # Set lockout
                lockout_key = f"{self._prefix}lockout:{identifier}"
                await redis_client.setex(
                    lockout_key,
                    self._lockout_seconds,
                    datetime.now(timezone.utc).isoformat()
                )
                logger.warning(f"Account locked for {identifier} after {attempts} failed attempts")
            
            return attempts, is_locked
            
        except Exception as e:
            logger.error(f"Failed to record failed attempt: {e}")
            return 0, False
    
    async def is_locked(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if an account is locked.
        
        Args:
            identifier: Email or IP address to check
        
        Returns:
            Tuple of (is_locked, remaining_lockout_seconds)
        """
        try:
            redis_client = await self.get_redis()
            lockout_key = f"{self._prefix}lockout:{identifier}"
            
            # Check lockout
            ttl = await redis_client.ttl(lockout_key)
            
            if ttl > 0:
                return True, ttl
            
            return False, 0
            
        except Exception as e:
            logger.error(f"Failed to check lockout status: {e}")
            return False, 0
    
    async def get_attempt_count(self, identifier: str) -> int:
        """
        Get the current number of failed attempts.
        
        Args:
            identifier: Email or IP address
        
        Returns:
            Number of failed attempts in current window
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}attempts:{identifier}"
            
            attempts = await redis_client.get(key)
            return int(attempts) if attempts else 0
            
        except Exception as e:
            logger.error(f"Failed to get attempt count: {e}")
            return 0
    
    async def clear_attempts(self, identifier: str) -> bool:
        """
        Clear failed login attempts (after successful login).
        
        Args:
            identifier: Email or IP address
        
        Returns:
            True if cleared successfully
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}attempts:{identifier}"
            lockout_key = f"{self._prefix}lockout:{identifier}"
            
            await redis_client.delete(key, lockout_key)
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear attempts: {e}")
            return False
    
    async def admin_unlock(self, identifier: str) -> bool:
        """
        Admin function to unlock a locked account.
        
        Args:
            identifier: Email or IP address to unlock
        
        Returns:
            True if unlocked successfully
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}attempts:{identifier}"
            lockout_key = f"{self._prefix}lockout:{identifier}"
            
            await redis_client.delete(key, lockout_key)
            logger.info(f"Admin unlocked account: {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to admin unlock: {e}")
            return False
    
    async def get_remaining_attempts(self, identifier: str) -> int:
        """
        Get remaining login attempts before lockout.
        
        Args:
            identifier: Email or IP address
        
        Returns:
            Number of remaining attempts
        """
        attempts = await self.get_attempt_count(identifier)
        return max(0, self._max_attempts - attempts)
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global instance
login_security = LoginSecurityService()
