"""
Time Tracker API - Main FastAPI Application
SEC-004, SEC-007, SEC-008, SEC-009, SEC-010, SEC-018, SEC-020: Security Hardened
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uuid

from app.config import settings
from app.database import get_db
from app.routers import auth, users, teams, projects, tasks, time_entries, reports, websocket
from app.routers import pay_rates, payroll, payroll_reports, monitoring
from app.routers import admin, export, sessions, invitations, approvals, report_templates
from app.routers import ip_security as ip_security_router
from app.routers import account_requests
from app.middleware import RateLimitMiddleware, rate_limiter, SecurityHeadersMiddleware, RequestValidationMiddleware
from app.exceptions import AppException

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    logger.info("Starting Time Tracker API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("Time Tracker API started successfully")
    yield
    logger.info("Shutting down Time Tracker API...")


# SEC-009: Disable docs in production
docs_url = "/docs" if settings.DEBUG else None
redoc_url = "/redoc" if settings.DEBUG else None
openapi_url = "/openapi.json" if settings.DEBUG else None

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A comprehensive time tracking and project management API with payroll features",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# SEC-018: Add request validation middleware first
app.add_middleware(RequestValidationMiddleware)

# SEC-007, SEC-020: Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# SEC-004: Add rate limiting middleware
app.add_middleware(RateLimitMiddleware, limiter=rate_limiter)

# SEC-008: Tightened CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "Accept",
        "Origin",
        "X-CSRF-Token",
    ],
    expose_headers=[
        "X-Process-Time",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
    max_age=600,
)

# SEC-009: TrustedHostMiddleware always enabled (not just non-DEBUG)
# Allow any host in DEBUG or TESTING mode
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS + ["*"] if (settings.DEBUG or settings.TESTING) else settings.ALLOWED_HOSTS,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security-related headers to all responses"""
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())[:8]

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id

    # SEC-020: Remove server identification
    if "Server" in response.headers:
        del response.headers["Server"]

    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Time Tracker API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
    }


# SEC-023: API versioning - Include routers with /api prefix
# Core routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(teams.router, prefix="/api/teams", tags=["Teams"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(time_entries.router, prefix="/api/time", tags=["Time Entries"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(websocket.router, prefix="/api/ws", tags=["WebSocket"])

# Payroll routes
app.include_router(pay_rates.router, tags=["Pay Rates"])
app.include_router(payroll.router, tags=["Payroll"])
app.include_router(payroll_reports.router, tags=["Payroll Reports"])

# Monitoring routes
app.include_router(monitoring.router, prefix="/api", tags=["Monitoring"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])

# Export routes
app.include_router(export.router, prefix="/api/export", tags=["Export"])

# Session management routes
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])

# Invitations and password reset routes
app.include_router(invitations.router, prefix="/api/auth", tags=["Invitations"])

# Time entry approval routes
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])

# IP Security routes
app.include_router(ip_security_router.router, prefix="/api/security/ip", tags=["IP Security"])

# Report Templates routes
app.include_router(report_templates.router, prefix="/api/reports", tags=["Report Templates"])

# Account Request routes (public + admin)
app.include_router(account_requests.router, prefix="/api/account-requests", tags=["Account Requests"])


# SEC-010: Custom exception handler for AppException
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions with safe error messages"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=getattr(exc, 'headers', None)
    )


# SEC-010: Global exception handler - sanitize errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler - never expose internal details"""
    request_id = str(uuid.uuid4())[:8]

    # Log the full error internally
    logger.error(f"[{request_id}] Unhandled exception: {exc}", exc_info=True)

    # Return sanitized error to client
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An internal error occurred. Please try again later.",
            "request_id": request_id
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        # SEC-018: Request size and timeout limits
        limit_concurrency=100,
        timeout_keep_alive=30,
    )




