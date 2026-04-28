"""B25: CORS startup configuration tests.

Verifies:
- `_assert_cors_not_fully_closed_in_production` raises when production has
  neither an exact-origins list nor a wildcard regex.
- The same helper does NOT raise in non-production envs.
- The same helper does NOT raise in production when at least one of the
  inputs is non-empty.
- `build_cors_origin_regex` returns None for empty wildcard domains and a
  valid regex string for configured ones.
- The startup log line `cors.config_resolved` is emitted with the resolved
  configuration when the module is reloaded under a valid configuration.
"""
import importlib
import logging
import re

import pytest

from app import main as app_main
from app.config import settings


def test_assert_raises_in_production_when_both_empty():
    with pytest.raises(RuntimeError, match="CORS is fully closed in production"):
        app_main._assert_cors_not_fully_closed_in_production(
            environment="production",
            exact_origins=[],
            origin_regex=None,
        )


def test_assert_does_not_raise_in_production_with_exact_origins():
    app_main._assert_cors_not_fully_closed_in_production(
        environment="production",
        exact_origins=["https://app.example.com"],
        origin_regex=None,
    )


def test_assert_does_not_raise_in_production_with_regex():
    app_main._assert_cors_not_fully_closed_in_production(
        environment="production",
        exact_origins=[],
        origin_regex=r"https?://[a-z0-9-]+\.example\.com",
    )


@pytest.mark.parametrize("env", ["development", "test", "staging"])
def test_assert_does_not_raise_outside_production(env):
    # Even with an empty config, only production blocks startup.
    app_main._assert_cors_not_fully_closed_in_production(
        environment=env,
        exact_origins=[],
        origin_regex=None,
    )


def test_build_cors_origin_regex_returns_none_when_no_wildcards(monkeypatch):
    monkeypatch.setattr(settings, "CORS_WILDCARD_DOMAINS", [])
    assert app_main.build_cors_origin_regex() is None


def test_build_cors_origin_regex_matches_subdomains(monkeypatch):
    monkeypatch.setattr(
        settings, "CORS_WILDCARD_DOMAINS", ["example.com", "test.com"]
    )
    pattern = app_main.build_cors_origin_regex()
    assert pattern is not None
    compiled = re.compile(pattern)
    assert compiled.fullmatch("https://tenant1.example.com")
    assert compiled.fullmatch("http://abc-corp.test.com")
    # Must NOT match the bare apex domain or unrelated hosts.
    assert not compiled.fullmatch("https://example.com")
    assert not compiled.fullmatch("https://evil.com")


def test_cors_config_resolved_log_emitted_on_reload(monkeypatch):
    """Reload app.main with a valid CORS config and assert the structured
    log identifier `cors.config_resolved` fires with the resolved fields."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", ["https://ok.example.com"])
    monkeypatch.setattr(settings, "CORS_WILDCARD_DOMAINS", ["example.com"])

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Capture(level=logging.INFO)
    target_logger = logging.getLogger("app.main")
    target_logger.addHandler(handler)
    try:
        importlib.reload(app_main)
    finally:
        target_logger.removeHandler(handler)

    matched = [r for r in captured if r.getMessage() == "cors.config_resolved"]
    assert matched, (
        "expected at least one log record with message 'cors.config_resolved'"
    )
    rec = matched[-1]
    assert getattr(rec, "exact_origins", None) == ["https://ok.example.com"]
    assert getattr(rec, "wildcard_enabled", None) is True
    assert getattr(rec, "environment", None) == "test"
    assert getattr(rec, "origin_regex", None) is not None
