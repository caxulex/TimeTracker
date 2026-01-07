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
from app.routers import api_keys  # SEC-020: API Key management
from app.routers import ai_features  # AI Feature Toggle System
from app.routers import companies  # Multi-tenancy / White-label support
from app.ai import ai_router  # AI Services (suggestions, anomalies)
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
    
    # Auto-seed AI features if not present
    try:
        await seed_ai_features_on_startup()
    except Exception as e:
        logger.warning(f"Could not auto-seed AI features: {e}")
    
    logger.info("Time Tracker API started successfully")
    yield
    logger.info("Shutting down Time Tracker API...")


async def seed_ai_features_on_startup():
    """Automatically seed AI features if the table is empty"""
    from sqlalchemy import text
    from app.database import async_session
    
    async with async_session() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM ai_feature_settings"))
        count = result.scalar()
        
        if count == 0:
            logger.info("Seeding AI features...")
            features = [
                ("ai_suggestions", "Time Entry Suggestions", "AI-powered suggestions for projects and tasks based on your work patterns", True, True, "gemini"),
                ("ai_anomaly_alerts", "Anomaly Detection", "Automatic detection of unusual work patterns like overtime or missing entries", True, True, "gemini"),
                ("ai_payroll_forecast", "Payroll Forecasting", "Predictive analytics for payroll and budget planning", False, True, "gemini"),
                ("ai_nlp_entry", "Natural Language Entry", "Create time entries using natural language", False, True, "gemini"),
                ("ai_report_summaries", "AI Report Summaries", "AI-generated insights and summaries in your reports", False, True, "gemini"),
                ("ai_task_estimation", "Task Duration Estimation", "AI-powered estimates for how long tasks will take", False, True, "gemini"),
            ]
            
            for f in features:
                await db.execute(
                    text("""
                        INSERT INTO ai_feature_settings 
                        (feature_id, feature_name, description, is_enabled, requires_api_key, api_provider)
                        VALUES (:fid, :fname, :desc, :enabled, :req_key, :provider)
                        ON CONFLICT (feature_id) DO NOTHING
                    """),
                    {"fid": f[0], "fname": f[1], "desc": f[2], "enabled": f[3], "req_key": f[4], "provider": f[5]}
                )
            
            await db.commit()
            logger.info(f"Seeded {len(features)} AI features")
        else:
            logger.info(f"AI features already exist ({count} features)")


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

# SEC-008: CORS origin validator for multi-tenant wildcard subdomain support
def is_origin_allowed(origin: str) -> bool:
    """
    Check if an origin is allowed for CORS.
    Supports:
    - Exact matches from ALLOWED_ORIGINS
    - Wildcard subdomain matches from CORS_WILDCARD_DOMAINS (e.g., *.example.com)
    """
    if not origin:
        return False
    
    # Exact match
    if origin in settings.ALLOWED_ORIGINS:
        return True
    
    # Parse origin to get hostname
    try:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        hostname = parsed.hostname or ''
        scheme = parsed.scheme or 'https'
    except Exception:
        return False
    
    # Check wildcard domains
    for base_domain in settings.CORS_WILDCARD_DOMAINS:
        # Allow exact base domain
        if hostname == base_domain:
            return True
        # Allow any subdomain of base domain (e.g., xyz-corp.timetracker.shaemarcus.com)
        if hostname.endswith(f'.{base_domain}'):
            return True
    
    return False


# SEC-008: Build complete origins list for CORS middleware
def get_all_cors_origins() -> list:
    """
    Get all allowed origins including wildcard domain expansions.
    Note: FastAPI CORSMiddleware doesn't support regex, so we use allow_origin_regex
    or handle dynamically with a custom middleware for full wildcard support.
    """
    origins = list(settings.ALLOWED_ORIGINS)
    # For non-wildcard usage, return exact list
    return origins


# SEC-008: Build CORS origin regex for wildcard subdomain support
def build_cors_origin_regex() -> str | None:
    """
    Build a regex pattern to match wildcard subdomains.
    Returns regex for CORS or None if no wildcard domains configured.
    """
    if not settings.CORS_WILDCARD_DOMAINS:
        return None
    
    # Build regex pattern for all wildcard domains
    # e.g., ["example.com", "test.com"] -> r"https?://.*\.(example\.com|test\.com)"
    escaped_domains = [domain.replace('.', r'\.') for domain in settings.CORS_WILDCARD_DOMAINS]
    domain_pattern = '|'.join(escaped_domains)
    return rf"https?://[a-zA-Z0-9-]+\.({domain_pattern})"


# SEC-008: Tightened CORS configuration with multi-tenant support
cors_origin_regex = build_cors_origin_regex()
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_all_cors_origins(),
    allow_origin_regex=cors_origin_regex,
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

# SEC-008: Build allowed hosts list including wildcard subdomains
def get_all_allowed_hosts() -> list:
    """
    Get all allowed hosts including wildcard patterns for subdomains.
    TrustedHostMiddleware supports wildcard patterns like *.example.com
    """
    hosts = list(settings.ALLOWED_HOSTS)
    
    # Add wildcard patterns for each base domain
    for base_domain in settings.CORS_WILDCARD_DOMAINS:
        wildcard_pattern = f"*.{base_domain}"
        if wildcard_pattern not in hosts:
            hosts.append(wildcard_pattern)
        # Also ensure base domain itself is allowed
        if base_domain not in hosts:
            hosts.append(base_domain)
    
    return hosts


# SEC-009: TrustedHostMiddleware with wildcard subdomain support
# Allow any host in DEBUG or TESTING mode
allowed_hosts_list = get_all_allowed_hosts() + ["*"] if (settings.DEBUG or settings.TESTING) else get_all_allowed_hosts()
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts_list,
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
    """Health check endpoint for monitoring and load balancers"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/health")
async def api_health_check():
    """
    Detailed health check endpoint with database and Redis status.
    Use this for comprehensive monitoring.
    """
    import redis.asyncio as redis_client
    from sqlalchemy import text
    from app.database import engine as async_engine
    
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {
            "database": "unknown",
            "redis": "unknown"
        }
    }
    
    # Check database connection
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)[:50]}"
        health_status["status"] = "degraded"
    
    # Check Redis connection
    try:
        redis = redis_client.from_url(settings.REDIS_URL)
        await redis.ping()
        await redis.close()
        health_status["checks"]["redis"] = "healthy"
    except Exception as e:
        health_status["checks"]["redis"] = f"unhealthy: {str(e)[:50]}"
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/api/version")
async def version_info():
    """
    Version and build information endpoint.
    Useful for debugging and deployment verification.
    """
    import sys
    import platform
    
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "python_version": sys.version.split()[0],
        "platform": platform.system(),
        "debug_mode": settings.DEBUG
    }


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

# SEC-020: API Key management routes (super admin only)
app.include_router(api_keys.router, prefix="/api", tags=["API Keys"])

# AI Feature Toggle System routes
app.include_router(ai_features.router, prefix="/api", tags=["AI Features"])

# AI Services routes (suggestions, anomalies)
app.include_router(ai_router, prefix="/api", tags=["AI Services"])

# Company / Multi-tenancy routes (White-label support)
app.include_router(companies.router, prefix="/api/companies", tags=["Companies"])


# SEC-010: Custom exception handler for AppException
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions with safe error messages"""
    content = exc.detail.copy() if isinstance(exc.detail, dict) else {"detail": exc.detail}
    # Include details if available (e.g., password requirements)
    if hasattr(exc, 'details') and exc.details:
        content['details'] = exc.details
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
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




