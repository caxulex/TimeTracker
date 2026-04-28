"""
Sentry Integration for Backend
Phase 3: Production Observability

Initializes Sentry error tracking for the FastAPI backend.
Only activates when SENTRY_DSN environment variable is set.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_initialized = False


def init_sentry() -> bool:
    """
    Initialize Sentry SDK for the backend.

    Returns:
        True if Sentry was initialized, False if skipped.
    """
    global _initialized

    if _initialized:
        return True

    from app.config import settings

    dsn: Optional[str] = getattr(settings, "SENTRY_DSN", None) or None

    if not dsn:
        logger.info("Sentry DSN not configured — error tracking disabled.")
        return False

    try:
        import sentry_sdk  # type: ignore[import-untyped]
        from sentry_sdk.integrations.fastapi import (
            FastApiIntegration,  # type: ignore[import-untyped]
        )
        from sentry_sdk.integrations.logging import (
            LoggingIntegration,  # type: ignore[import-untyped]
        )
        from sentry_sdk.integrations.starlette import (
            StarletteIntegration,  # type: ignore[import-untyped]
        )

        environment = getattr(settings, "ENVIRONMENT", "development")
        app_version = getattr(settings, "APP_VERSION", "unknown")
        is_production = environment == "production"

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=f"timetracker-backend@{app_version}",
            traces_sample_rate=0.1 if is_production else 1.0,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                LoggingIntegration(
                    level=logging.WARNING,
                    event_level=logging.ERROR,
                ),
            ],
            before_send_transaction=_filter_transactions,
            before_send=_sanitize_event,
        )

        _initialized = True
        logger.info(
            f"Sentry initialized for environment '{environment}' "
            f"(traces_sample_rate={'0.1' if is_production else '1.0'})"
        )
        return True

    except ImportError:
        logger.warning(
            "sentry-sdk not installed — error tracking disabled. "
            "Install with: pip install sentry-sdk[fastapi]"
        )
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
        return False


def _filter_transactions(event: dict, hint: dict) -> Optional[dict]:
    """Filter out noisy transactions like health checks."""
    transaction_name = event.get("transaction", "")

    skip_transactions = [
        "/health",
        "/api/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    if transaction_name in skip_transactions:
        return None

    return event


def _sanitize_event(event: dict, hint: dict) -> Optional[dict]:
    """Sanitize sensitive data from Sentry events before sending."""
    if "request" in event:
        headers = event["request"].get("headers", {})
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[Filtered]"

    return event


def is_initialized() -> bool:
    """Check if Sentry has been initialized."""
    return _initialized
