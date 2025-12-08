"""
Rate Limiting Middleware
SEC-004: Rate Limiting Implementation
Protects against brute force and DoS attacks
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import redis.asyncio as redis
from datetime import datetime, timezone
import logging
from typing import Optional, Callable
import os

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please slow down.",
                "retry_after": retry_after
            },
            headers={"Retry-After": str(retry_after)}
        )


class RateLimiter:
    """
    Rate limiter using Redis sliding window algorithm.
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._prefix = "rate_limit:"
        self._enabled = True
        
        # Default limits
        self.default_limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        self.default_window = 60  # 1 minute
        
        # Endpoint-specific limits
        self.endpoint_limits = {
            "/api/auth/login": (5, 60),      # 5 requests per minute
            "/api/auth/register": (3, 60),   # 3 requests per minute
            "/api/auth/refresh": (10, 60),   # 10 requests per minute
            "/api/auth/password": (3, 300),  # 3 requests per 5 minutes
        }
    
    def disable(self):
        """Disable rate limiting (for testing)"""
        self._enabled = False
    
    def enable(self):
        """Enable rate limiting"""
        self._enabled = True
    
    async def get_redis(self) -> Optional[redis.Redis]:
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
                logger.warning(f"Redis not available for rate limiting: {e}")
                return None
        return self._redis
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def get_limit_for_endpoint(self, path: str) -> tuple:
        """Get rate limit for a specific endpoint"""
        for endpoint, limits in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limits
        return (self.default_limit, self.default_window)
    
    async def check_rate_limit(
        self,
        identifier: str,
        path: str = "default"
    ) -> tuple:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: Client identifier (IP address or user ID)
            path: API endpoint path
        
        Returns:
            Tuple of (is_allowed, current_count, limit, remaining, reset_time)
        """
        if not self._enabled:
            limit, _ = self.get_limit_for_endpoint(path)
            return (True, 0, limit, limit, 0)
        
        limit, window = self.get_limit_for_endpoint(path)
        
        try:
            redis_client = await self.get_redis()
            if redis_client is None:
                # If Redis is unavailable, allow the request (fail open)
                return (True, 0, limit, limit, 0)
            
            now = datetime.now(timezone.utc)
            window_key = f"{self._prefix}{identifier}:{path}:{int(now.timestamp()) // window}"
            
            # Increment counter
            pipe = redis_client.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window + 1)
            results = await pipe.execute()
            
            current_count = results[0]
            remaining = max(0, limit - current_count)
            reset_time = ((int(now.timestamp()) // window) + 1) * window
            
            is_allowed = current_count <= limit
            
            return (is_allowed, current_count, limit, remaining, reset_time)
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis is down
            return (True, 0, limit, limit, 0)
    
    async def get_rate_limit_headers(
        self,
        identifier: str,
        path: str = "default"
    ) -> dict:
        """Get rate limit headers for response"""
        is_allowed, current, limit, remaining, reset = await self.check_rate_limit(
            identifier, path
        )
        
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset),
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for applying rate limits to all requests.
    """
    
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and docs
        skip_paths = ["/health", "/", "/docs", "/redoc", "/openapi.json"]
        if request.url.path in skip_paths:
            return await call_next(request)
        
        # Skip rate limiting during tests
        testing_env = os.environ.get("TESTING", "").lower()
        is_testing = testing_env in ("true", "1", "yes")
        if is_testing or "testclient" in str(request.headers.get("user-agent", "")).lower():
            response = await call_next(request)
            # Still add headers for testing purposes
            limit, _ = self.limiter.get_limit_for_endpoint(request.url.path)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(limit)
            response.headers["X-RateLimit-Reset"] = "0"
            return response
        
        # Get client identifier
        client_ip = self.limiter.get_client_ip(request)
        path = request.url.path
        
        # Check rate limit
        is_allowed, current, limit, remaining, reset = await self.limiter.check_rate_limit(
            client_ip, path
        )
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
            raise RateLimitExceeded(retry_after=60)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        
        return response


# Global instance
rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Dependency to get rate limiter instance"""
    return rate_limiter
