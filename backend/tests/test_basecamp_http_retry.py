"""Tests for the 429-aware retry/backoff layer in basecamp_service.

The feature spec lives in the PR ``feat/basecamp-rate-limit-backoff``.
We assert behaviour at the unit level by driving
``_http_request_with_retry`` against a mocked ``httpx.AsyncClient`` and
patching ``asyncio.sleep`` to avoid real waiting.

Covered scenarios (from acceptance criteria):

* Single 429 then 200 -> caller sees the 200.
* Three 429s then give up -> the final 429 is returned (caller will then
  raise as before).
* ``Retry-After: 5`` -> wait honoured (clamped + jittered).
* ``Retry-After: foo`` (invalid) -> falls back to exponential backoff.
* Missing ``Retry-After`` -> exponential backoff (2s, 4s, 8s pattern).
* ``Retry-After: 999`` -> clamped to ``HTTP_429_MAX_SINGLE_WAIT_SECONDS``.
* Each retry attempt is logged as ``basecamp.http.429.retry``.
* HTTP-date form of ``Retry-After`` parses correctly.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services import basecamp_service
from app.services.basecamp_service import (
    HTTP_429_MAX_RETRIES,
    HTTP_429_MAX_SINGLE_WAIT_SECONDS,
    _http_request_with_retry,
    _parse_retry_after,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int, headers: dict | None = None) -> httpx.Response:
    """Build a real ``httpx.Response`` so ``status_code``/``headers`` behave."""
    return httpx.Response(
        status_code,
        headers=headers or {},
        request=httpx.Request("GET", "https://3.basecampapi.com/test"),
    )


def _make_client(responses: list[httpx.Response]) -> MagicMock:
    """A mock client whose ``get`` returns the queued responses in order."""
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=responses)
    return client


@pytest.fixture
def no_sleep(monkeypatch):
    """Replace ``asyncio.sleep`` inside the module with an instant no-op
    that still records the sleep durations for assertions."""
    durations: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        durations.append(seconds)

    monkeypatch.setattr(basecamp_service.asyncio, "sleep", fake_sleep)
    return durations


@pytest.fixture
def no_jitter(monkeypatch):
    """Make the random jitter deterministic (always 0) for assertions."""
    monkeypatch.setattr(
        basecamp_service.random, "uniform", lambda a, b: 0.0
    )


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------


class TestParseRetryAfter:
    def test_none_returns_none(self):
        assert _parse_retry_after(None) is None

    def test_blank_returns_none(self):
        assert _parse_retry_after("   ") is None

    def test_integer_seconds(self):
        assert _parse_retry_after("5") == 5.0

    def test_float_seconds(self):
        assert _parse_retry_after("2.5") == 2.5

    def test_negative_clamps_to_zero(self):
        assert _parse_retry_after("-10") == 0.0

    def test_invalid_string_returns_none(self):
        assert _parse_retry_after("foo") is None

    def test_http_date_future(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        value = format_datetime(future, usegmt=True)
        parsed = _parse_retry_after(value)
        assert parsed is not None
        # Allow a small clock-skew window.
        assert 5 <= parsed <= 15

    def test_http_date_past_clamps_to_zero(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        value = format_datetime(past, usegmt=True)
        assert _parse_retry_after(value) == 0.0


# ---------------------------------------------------------------------------
# _http_request_with_retry
# ---------------------------------------------------------------------------


class TestHttpRequestWithRetry:
    @pytest.mark.asyncio
    async def test_immediate_200_no_retry(self, no_sleep):
        client = _make_client([_make_response(200)])
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        assert resp.status_code == 200
        assert client.get.await_count == 1
        assert no_sleep == []

    @pytest.mark.asyncio
    async def test_single_429_then_200(self, no_sleep, no_jitter, caplog):
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "5"}),
                _make_response(200),
            ]
        )
        with caplog.at_level("INFO"):
            resp = await _http_request_with_retry(
                client, "GET", "https://3.basecampapi.com/test"
            )
        assert resp.status_code == 200
        assert client.get.await_count == 2
        # Retry-After=5 honoured (no jitter under the fixture).
        assert no_sleep == [5.0]
        assert any(
            "basecamp.http.429.retry" in rec.message
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_three_429s_then_give_up(self, no_sleep, no_jitter):
        # 4 calls total: initial + 3 retries, all 429.
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "1"})
                for _ in range(HTTP_429_MAX_RETRIES + 1)
            ]
        )
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        # The original 429 is returned so the caller's existing non-200
        # handling raises BasecampAPIError as before.
        assert resp.status_code == 429
        assert client.get.await_count == HTTP_429_MAX_RETRIES + 1
        # Three sleeps for three retries.
        assert len(no_sleep) == HTTP_429_MAX_RETRIES

    @pytest.mark.asyncio
    async def test_missing_retry_after_uses_exponential_backoff(
        self, no_sleep, no_jitter
    ):
        client = _make_client(
            [
                _make_response(429),
                _make_response(429),
                _make_response(429),
                _make_response(200),
            ]
        )
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        assert resp.status_code == 200
        # Exponential: 2, 4, 8 with no jitter (no_jitter fixture).
        assert no_sleep == [2.0, 4.0, 8.0]

    @pytest.mark.asyncio
    async def test_invalid_retry_after_uses_exponential_backoff(
        self, no_sleep, no_jitter
    ):
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "foo"}),
                _make_response(200),
            ]
        )
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        assert resp.status_code == 200
        # First-attempt exponential fallback is 2s.
        assert no_sleep == [2.0]

    @pytest.mark.asyncio
    async def test_retry_after_exceeding_cap_is_clamped(
        self, no_sleep, no_jitter
    ):
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "999"}),
                _make_response(200),
            ]
        )
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        assert resp.status_code == 200
        assert no_sleep == [HTTP_429_MAX_SINGLE_WAIT_SECONDS]

    @pytest.mark.asyncio
    async def test_jitter_is_added(self, no_sleep, monkeypatch):
        # Force jitter to exactly 0.42 to verify it's added to the base wait.
        monkeypatch.setattr(
            basecamp_service.random, "uniform", lambda a, b: 0.42
        )
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "3"}),
                _make_response(200),
            ]
        )
        await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        assert no_sleep == [pytest.approx(3.42)]

    @pytest.mark.asyncio
    async def test_total_wait_budget_caps_retries(
        self, no_sleep, no_jitter, monkeypatch
    ):
        # Shrink the total budget so a single big Retry-After exhausts it.
        monkeypatch.setattr(
            basecamp_service, "HTTP_429_MAX_TOTAL_WAIT_SECONDS", 5.0
        )
        # First retry would wait 30s (clamped from 999) -> exceeds 5s budget.
        client = _make_client(
            [
                _make_response(429, {"Retry-After": "999"}),
                _make_response(200),  # would-be success, never reached
            ]
        )
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        # Budget exhausted before the first sleep -> 429 returned.
        assert resp.status_code == 429
        assert no_sleep == []
        assert client.get.await_count == 1

    @pytest.mark.asyncio
    async def test_non_429_5xx_returned_unchanged(self, no_sleep):
        client = _make_client([_make_response(503)])
        resp = await _http_request_with_retry(
            client, "GET", "https://3.basecampapi.com/test"
        )
        # Only 429 is retried; 5xx propagates immediately.
        assert resp.status_code == 503
        assert client.get.await_count == 1
        assert no_sleep == []
