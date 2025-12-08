"""
Security Middleware
SEC-007, SEC-020: Security Headers Implementation
Adds security headers to all responses
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    Implements OWASP security header recommendations.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Content Security Policy (CSP)
        # Adjust based on your application needs
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # May need adjustment for React
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' wss: ws: https:",
            "frame-ancestors 'self'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ]
        
        if not settings.DEBUG:
            # More restrictive CSP for production
            csp_directives = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https:",
                "font-src 'self'",
                "connect-src 'self' wss: https:",
                "frame-ancestors 'self'",
                "form-action 'self'",
                "base-uri 'self'",
                "object-src 'none'",
                "upgrade-insecure-requests",
            ]
        
        # Apply security headers
        security_headers = {
            # Prevent clickjacking
            "X-Frame-Options": "SAMEORIGIN",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # XSS Protection (legacy, but still useful for older browsers)
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": "; ".join(csp_directives),
            
            # Permissions Policy (formerly Feature-Policy)
            "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
            
            # Cache Control for sensitive data
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        
        # HSTS - Only in production with HTTPS
        if settings.ENVIRONMENT == "production":
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Remove server identification headers
        # Note: Some of these may need to be configured at the web server level
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]
        
        # Apply all security headers
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    SEC-018: Request size and timeout validation middleware.
    """
    
    MAX_CONTENT_LENGTH = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert MB to bytes
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > self.MAX_CONTENT_LENGTH:
                logger.warning(
                    f"Request too large from {request.client.host}: {content_length} bytes"
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "request_too_large",
                        "message": f"Request body too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB",
                        "max_size_bytes": self.MAX_CONTENT_LENGTH
                    }
                )
        
        response = await call_next(request)
        return response
