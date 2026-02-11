"""
Tests for Sentry integration (Phase 3: Production Observability).
Verifies the app starts correctly both WITH and WITHOUT SENTRY_DSN set.
"""

import pytest
from unittest.mock import patch, MagicMock


def test_sentry_init_skips_without_dsn():
    """init_sentry should return False when no DSN is set."""
    import app.integrations.sentry as sentry_module

    sentry_module._initialized = False

    from app.config import settings
    original_dsn = getattr(settings, "SENTRY_DSN", None)
    try:
        settings.SENTRY_DSN = None
        result = sentry_module.init_sentry()
        assert result is False
    finally:
        settings.SENTRY_DSN = original_dsn
        sentry_module._initialized = False


def test_sentry_init_with_dsn():
    """init_sentry should return True and call sentry_sdk.init when DSN is provided."""
    import app.integrations.sentry as sentry_module

    sentry_module._initialized = False

    from app.config import settings
    original_dsn = settings.SENTRY_DSN
    try:
        settings.SENTRY_DSN = "https://examplePublicKey@o0.ingest.sentry.io/0"

        with patch("sentry_sdk.init") as mock_init:
            result = sentry_module.init_sentry()
            assert result is True
            mock_init.assert_called_once()

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["dsn"] == "https://examplePublicKey@o0.ingest.sentry.io/0"
            assert "environment" in call_kwargs
            assert "release" in call_kwargs
            assert "traces_sample_rate" in call_kwargs
    finally:
        settings.SENTRY_DSN = original_dsn
        sentry_module._initialized = False


def test_sentry_is_initialized_flag():
    """is_initialized should reflect the current state."""
    import app.integrations.sentry as sentry_module

    sentry_module._initialized = False
    assert sentry_module.is_initialized() is False

    sentry_module._initialized = True
    assert sentry_module.is_initialized() is True

    # Reset
    sentry_module._initialized = False


def test_sentry_skips_if_already_initialized():
    """If already initialized, init_sentry should return True immediately."""
    import app.integrations.sentry as sentry_module

    sentry_module._initialized = True
    try:
        result = sentry_module.init_sentry()
        assert result is True
    finally:
        sentry_module._initialized = False


def test_sanitize_event_filters_sensitive_headers():
    """_sanitize_event should filter authorization headers."""
    from app.integrations.sentry import _sanitize_event

    event = {
        "request": {
            "headers": {
                "authorization": "Bearer secret-token",
                "cookie": "session=abc",
                "content-type": "application/json",
            }
        }
    }

    result = _sanitize_event(event, {})
    assert result is not None
    assert result["request"]["headers"]["authorization"] == "[Filtered]"
    assert result["request"]["headers"]["cookie"] == "[Filtered]"
    assert result["request"]["headers"]["content-type"] == "application/json"


def test_filter_transactions_skips_health_checks():
    """_filter_transactions should filter out health check endpoints."""
    from app.integrations.sentry import _filter_transactions

    health_event = {"transaction": "/health"}
    assert _filter_transactions(health_event, {}) is None

    api_health_event = {"transaction": "/api/health"}
    assert _filter_transactions(api_health_event, {}) is None

    real_event = {"transaction": "/api/time/entries"}
    assert _filter_transactions(real_event, {}) is not None
