"""
Token Blacklist Service
SEC-002: JWT Token Blacklist Implementation
Uses Redis for persistent token blacklist with automatic expiration
"""

import redis.asyncio as redis
from typing import Optional
from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """
    Service for managing JWT token blacklist using Redis.
    Tokens are blacklisted on logout and checked during authentication.
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._prefix = "token_blacklist:"
    
    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis.ping()
                logger.info("Token blacklist Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis for token blacklist: {e}")
                raise
        return self._redis
    
    async def blacklist_token(self, jti: str, expires_in: int) -> bool:
        """
        Add a token's JTI to the blacklist.
        
        Args:
            jti: JWT ID (unique identifier for the token)
            expires_in: Time in seconds until token expires (TTL for Redis key)
        
        Returns:
            True if successfully blacklisted, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}{jti}"
            
            # Store with automatic expiration matching token expiry
            # Add some buffer time (60 seconds) to ensure we don't miss edge cases
            await redis_client.setex(
                key,
                expires_in + 60,
                datetime.now(timezone.utc).isoformat()
            )
            
            logger.info(f"Token {jti[:8]}... blacklisted for {expires_in}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False
    
    async def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token's JTI is in the blacklist.
        
        Args:
            jti: JWT ID to check
        
        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            key = f"{self._prefix}{jti}"
            exists = await redis_client.exists(key)
            return exists > 0
            
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # Fail secure - if we can't check, assume it might be blacklisted
            # In production, you might want different behavior
            return False
    
    async def blacklist_user_tokens(self, user_id: int) -> bool:
        """
        Blacklist all tokens for a specific user (e.g., on password change).
        This is a marker that invalidates all tokens issued before this time.
        
        Args:
            user_id: The user ID to invalidate tokens for
        
        Returns:
            True if successfully set, False otherwise
        """
        try:
            redis_client = await self.get_redis()
            key = f"user_tokens_invalid:{user_id}"
            
            # Set invalidation timestamp with long TTL (30 days)
            await redis_client.setex(
                key,
                30 * 24 * 60 * 60,  # 30 days
                datetime.now(timezone.utc).isoformat()
            )
            
            logger.info(f"All tokens invalidated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate user tokens: {e}")
            return False
    
    async def get_user_tokens_invalid_after(self, user_id: int) -> Optional[datetime]:
        """
        Get the timestamp after which all tokens for a user are invalid.
        
        Args:
            user_id: The user ID to check
        
        Returns:
            datetime if invalidation is set, None otherwise
        """
        try:
            redis_client = await self.get_redis()
            key = f"user_tokens_invalid:{user_id}"
            
            timestamp_str = await redis_client.get(key)
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user token invalidation: {e}")
            return None
    
    async def get_blacklist_stats(self) -> dict:
        """Get statistics about the token blacklist"""
        try:
            redis_client = await self.get_redis()
            
            # Count blacklisted tokens
            cursor = 0
            count = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, 
                    match=f"{self._prefix}*",
                    count=100
                )
                count += len(keys)
                if cursor == 0:
                    break
            
            return {
                "blacklisted_tokens": count,
                "redis_connected": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get blacklist stats: {e}")
            return {
                "blacklisted_tokens": 0,
                "redis_connected": False,
                "error": str(e)
            }
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global instance
token_blacklist = TokenBlacklistService()
