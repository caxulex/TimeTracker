"""
Tests for structured JSON logging (Phase 3: Production Observability).
Verifies:
(a) JSON log format in production mode
(b) request_id appears in logs
(c) X-Request-ID header is present in responses
"""

import json
import logging
import pytest
from httpx import AsyncClient, ASGITransport

from app.logging_config import (
    configure_logging,
    request_id_var,
    RequestIdFilter,
    JsonLogFormatter,
)


class TestJsonLogFormatter:
    """Test the JSON log formatter directly."""

    def test_json_format_output(self):
        """JSON formatter produces valid JSON with required fields."""
        formatter = JsonLogFormatter()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=42,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        record.request_id = "abc12345"  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["request_id"] == "abc12345"
        assert parsed["module"] == "test_file"
        assert "function" in parsed
        assert "timestamp" in parsed
        assert "logger" in parsed

    def test_json_format_with_exception(self):
        """JSON formatter includes exception details."""
        formatter = JsonLogFormatter()

        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test_file.py",
            lineno=42,
            msg="Error occurred",
            args=None,
            exc_info=exc_info,
        )
        record.request_id = "err12345"  # type: ignore[attr-defined]

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test error" in parsed["exception"]["message"]


class TestRequestIdFilter:
    """Test the request_id logging filter."""

    def test_filter_injects_request_id(self):
        """Filter should inject request_id from context var."""
        filt = RequestIdFilter()

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="test", args=None, exc_info=None,
        )

        token = request_id_var.set("test-req-123")
        try:
            result = filt.filter(record)
            assert result is True
            assert record.request_id == "test-req-123"  # type: ignore[attr-defined]
        finally:
            request_id_var.reset(token)

    def test_filter_uses_default_when_no_request(self):
        """Filter should use 'no-request' when context var is not set."""
        filt = RequestIdFilter()

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="test", args=None, exc_info=None,
        )

        token = request_id_var.set(None)
        try:
            filt.filter(record)
            assert record.request_id == "no-request"  # type: ignore[attr-defined]
        finally:
            request_id_var.reset(token)


class TestConfigureLogging:
    """Test logging configuration setup."""

    def test_configure_json_for_production(self):
        """Production environment should use JSON formatter."""
        configure_logging(
            log_level="INFO",
            environment="production",
            log_format="json",
        )

        root_logger = logging.getLogger()
        has_json_formatter = any(
            isinstance(h.formatter, JsonLogFormatter)
            for h in root_logger.handlers
        )
        assert has_json_formatter, "Production should use JsonLogFormatter"

    def test_configure_standard_for_development(self):
        """Development environment should use standard formatter."""
        configure_logging(
            log_level="INFO",
            environment="development",
            log_format="standard",
        )

        root_logger = logging.getLogger()
        has_json_formatter = any(
            isinstance(h.formatter, JsonLogFormatter)
            for h in root_logger.handlers
        )
        assert not has_json_formatter, "Development should not use JsonLogFormatter"


@pytest.mark.asyncio
async def test_request_id_in_response_header():
    """Every response should have X-Request-ID header."""
    from app.main import app

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert "x-request-id" in response.headers

        request_id = response.headers["x-request-id"]
        assert len(request_id) == 8


@pytest.mark.asyncio
async def test_different_requests_get_different_ids():
    """Each request should get a unique request_id."""
    from app.main import app

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp1 = await client.get("/health")
        resp2 = await client.get("/health")

        id1 = resp1.headers["x-request-id"]
        id2 = resp2.headers["x-request-id"]

        assert id1 != id2, "Each request should get a unique request_id"
