"""
Tests to verify that production error responses never leak
stack traces, file paths, or internal details.
SEC-010: Sanitized Error Responses verification
Phase 1: Critical Safety Net
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from fastapi import APIRouter

from app.main import app
from app.config import settings


# Create a temporary test router that deliberately raises an unhandled exception
_test_router = APIRouter()

@_test_router.get("/api/__test__/force-500")
async def _force_500():
    """Test-only endpoint that raises an unhandled exception."""
    raise RuntimeError("Simulated internal failure — DB connection exploded")

# Register it once (idempotent — won't break if run multiple times)
app.include_router(_test_router)


@pytest.mark.asyncio
async def test_unhandled_exception_returns_sanitized_response():
    """
    Hit an endpoint that raises an unhandled RuntimeError and verify the
    global exception handler returns a safe response with no traceback.
    """
    # raise_app_exceptions=False ensures we get the HTTP response
    # instead of the exception propagating through the test transport.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/__test__/force-500")

    assert response.status_code == 500

    body = response.json()
    body_text = str(body).lower()

    # Must NOT contain Python traceback indicators
    assert "traceback" not in body_text, "Response contains 'traceback'"
    assert "file \"" not in body_text, "Response contains file path reference"
    assert ".py\"" not in body_text, "Response contains .py file reference"
    assert "db connection exploded" not in body_text, \
        "Response leaks internal error message"
    assert "runtimeerror" not in body_text, \
        "Response leaks exception class name"

    # Verify it has the sanitized structure
    assert "request_id" in body, "500 response missing request_id for tracing"
    assert body["error"] == "internal_error"
    assert body["message"] == "An internal error occurred. Please try again later."


@pytest.mark.asyncio
async def test_404_does_not_leak_internals():
    """A 404 response should not include any internal details."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/this-route-does-not-exist-at-all")

    body_text = str(response.json()).lower()
    assert response.status_code in [404, 405]
    assert "traceback" not in body_text
    assert "file \"" not in body_text


@pytest.mark.asyncio
async def test_docs_hidden_when_debug_false():
    """
    When DEBUG=false, /docs, /redoc, /openapi.json should return 404.
    This test only validates if the app was started with DEBUG=false.
    """
    if settings.DEBUG:
        pytest.skip("DEBUG is True in test environment — docs are expected to be available")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        docs_response = await client.get("/docs")
        redoc_response = await client.get("/redoc")
        openapi_response = await client.get("/openapi.json")

    assert docs_response.status_code == 404, "/docs should be disabled in production"
    assert redoc_response.status_code == 404, "/redoc should be disabled in production"
    assert openapi_response.status_code == 404, "/openapi.json should be disabled in production"
