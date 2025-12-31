"""
AI Cache Manager

Manages Redis caching for AI responses to reduce API costs and improve latency.
Uses existing Redis infrastructure from the application.
"""

import json
import hashlib
from typing import Optional, Any, Dict
from datetime import datetime, timezone
import redis.asyncio as redis

from app.config import settings
from app.ai.config import ai_settings


class AICacheManager:
    """
    Manages caching of AI responses using Redis.
    
    Cache key patterns:
    - ai:suggestions:{user_id}:{context_hash}
    - ai:anomalies:{date}
    - ai:user_context:{user_id}
    - ai:forecast:{period_id}
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis: Optional[redis.Redis] = redis_client
        self._prefix = "ai"

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    def _make_key(self, *parts) -> str:
        """Create cache key from parts (accepts any type, converts to str)."""
        return f"{self._prefix}:{':'.join(str(p) for p in parts)}"

    def _hash_context(self, context: Dict[str, Any]) -> str:
        """Create hash of context for cache key."""
        context_str = json.dumps(context, sort_keys=True, default=str)
        return hashlib.md5(context_str.encode()).hexdigest()[:12]

    # ============================================
    # SUGGESTION CACHING
    # ============================================

    async def get_suggestion_cache(
        self,
        user_id: int,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached suggestions for user context."""
        try:
            r = await self.get_redis()
            context_hash = self._hash_context(context)
            key = self._make_key("suggestions", user_id, context_hash)
            
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    async def set_suggestion_cache(
        self,
        user_id: int,
        context: Dict[str, Any],
        suggestions: Dict[str, Any]
    ) -> bool:
        """Cache suggestions for user context."""
        try:
            r = await self.get_redis()
            context_hash = self._hash_context(context)
            key = self._make_key("suggestions", user_id, context_hash)
            
            await r.setex(
                key,
                ai_settings.CACHE_TTL_SUGGESTIONS,
                json.dumps(suggestions, default=str)
            )
            return True
        except Exception:
            return False

    # ============================================
    # ANOMALY CACHING
    # ============================================

    async def get_anomaly_cache(
        self,
        date: str,  # YYYY-MM-DD format
        user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached anomaly results."""
        try:
            r = await self.get_redis()
            if user_id:
                key = self._make_key("anomalies", date, user_id)
            else:
                key = self._make_key("anomalies", date, "all")
            
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    async def set_anomaly_cache(
        self,
        date: str,
        anomalies: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> bool:
        """Cache anomaly results."""
        try:
            r = await self.get_redis()
            if user_id:
                key = self._make_key("anomalies", date, user_id)
            else:
                key = self._make_key("anomalies", date, "all")
            
            await r.setex(
                key,
                ai_settings.CACHE_TTL_ANOMALIES,
                json.dumps(anomalies, default=str)
            )
            return True
        except Exception:
            return False

    # ============================================
    # USER CONTEXT CACHING
    # ============================================

    async def get_user_context(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user context for AI features."""
        try:
            r = await self.get_redis()
            key = self._make_key("user_context", user_id)
            
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    async def set_user_context(
        self,
        user_id: int,
        context: Dict[str, Any]
    ) -> bool:
        """Cache user context."""
        try:
            r = await self.get_redis()
            key = self._make_key("user_context", user_id)
            
            await r.setex(
                key,
                ai_settings.CACHE_TTL_USER_CONTEXT,
                json.dumps(context, default=str)
            )
            return True
        except Exception:
            return False

    # ============================================
    # FORECAST CACHING (Phase 2)
    # ============================================

    async def get_forecast_cache(
        self,
        forecast_type: str,
        entity_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached forecast results."""
        try:
            r = await self.get_redis()
            key = self._make_key("forecast", forecast_type, entity_id)
            
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    async def set_forecast_cache(
        self,
        forecast_type: str,
        entity_id: int,
        forecast: Dict[str, Any]
    ) -> bool:
        """Cache forecast results."""
        try:
            r = await self.get_redis()
            key = self._make_key("forecast", forecast_type, entity_id)
            
            await r.setex(
                key,
                ai_settings.CACHE_TTL_FORECASTS,
                json.dumps(forecast, default=str)
            )
            return True
        except Exception:
            return False

    # ============================================
    # RATE LIMITING
    # ============================================

    async def check_rate_limit(
        self,
        user_id: int,
        window_minutes: int = 1
    ) -> tuple[bool, int]:
        """
        Check if user is within rate limit.
        Returns (is_allowed, current_count).
        """
        try:
            r = await self.get_redis()
            key = self._make_key("ratelimit", user_id, window_minutes)
            
            current = await r.get(key)
            if current is None:
                # First request in window
                await r.setex(key, window_minutes * 60, "1")
                return True, 1
            
            count = int(current)
            limit = ai_settings.REQUESTS_PER_MINUTE if window_minutes == 1 else ai_settings.REQUESTS_PER_HOUR
            
            if count >= limit:
                return False, count
            
            await r.incr(key)
            return True, count + 1
        except Exception:
            # On error, allow request
            return True, 0

    async def increment_rate_limit(self, user_id: int) -> int:
        """Increment rate limit counter. Returns new count."""
        try:
            r = await self.get_redis()
            key = self._make_key("ratelimit", user_id, 1)
            
            # Use pipeline for atomic operation
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            results = await pipe.execute()
            return results[0]
        except Exception:
            return 0

    # ============================================
    # UTILITY METHODS
    # ============================================

    async def invalidate_user_cache(self, user_id: int) -> bool:
        """Invalidate all cache for a user."""
        try:
            r = await self.get_redis()
            
            # Find all keys for this user
            pattern = self._make_key("*", user_id, "*")
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)
            
            # Also check user context
            keys.append(self._make_key("user_context", user_id))
            
            if keys:
                await r.delete(*keys)
            return True
        except Exception:
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        try:
            r = await self.get_redis()
            
            stats = {
                "suggestion_keys": 0,
                "anomaly_keys": 0,
                "user_context_keys": 0,
                "ratelimit_keys": 0,
            }
            
            async for key in r.scan_iter(match=f"{self._prefix}:suggestions:*"):
                stats["suggestion_keys"] += 1
            async for key in r.scan_iter(match=f"{self._prefix}:anomalies:*"):
                stats["anomaly_keys"] += 1
            async for key in r.scan_iter(match=f"{self._prefix}:user_context:*"):
                stats["user_context_keys"] += 1
            async for key in r.scan_iter(match=f"{self._prefix}:ratelimit:*"):
                stats["ratelimit_keys"] += 1
            
            return stats
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Factory function for dependency injection
async def get_cache_manager() -> AICacheManager:
    """Get cache manager instance."""
    return AICacheManager()
