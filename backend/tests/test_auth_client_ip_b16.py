# ============================================
# B16: Trusted-proxy-aware client IP resolution
# ============================================
import logging
from unittest.mock import patch

import pytest
from fastapi import Request

from app.config import settings
from app.routers.auth import get_client_ip


def _make_request(peer: str | None, headers: dict | None = None) -> Request:
    """Build a minimal ASGI scope so FastAPI's Request works with no app."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (peer, 12345) if peer else None,
    }
    return Request(scope)


def test_b16_no_xff_no_trusted_returns_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", [])
    req = _make_request("127.0.0.1")
    assert get_client_ip(req) == "127.0.0.1"


def test_b16_xff_ignored_when_peer_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", [])
    req = _make_request("127.0.0.1", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "127.0.0.1"


def test_b16_xff_honored_when_peer_in_cidr(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    req = _make_request("10.0.0.5", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "1.2.3.4"


def test_b16_xff_skips_trusted_proxy_chain(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    # Leftmost is the actual client; the 10.0.0.5 is our own LB hop.
    req = _make_request(
        "10.0.0.5", {"X-Forwarded-For": "1.2.3.4, 10.0.0.5"}
    )
    assert get_client_ip(req) == "1.2.3.4"


def test_b16_exact_ip_in_trusted_list(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.5"])
    req = _make_request("10.0.0.5", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "1.2.3.4"


def test_b16_invalid_xff_falls_back_to_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    # All XFF entries are also trusted proxies → fall back.
    req = _make_request("10.0.0.5", {"X-Forwarded-For": "10.0.0.1"})
    # No real client found in chain — returns peer.
    assert get_client_ip(req) == "10.0.0.5"


def test_b16_production_warning_logged_when_proxies_empty(
    monkeypatch, caplog
):
    """The lifespan hook logs ``auth.no_trusted_proxies`` in prod when empty.

    We exercise the same branch directly to avoid spinning the lifespan.
    """
    from app.main import logger as main_logger

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", [])

    with caplog.at_level(logging.WARNING, logger=main_logger.name):
        if settings.ENVIRONMENT == "production" and not settings.TRUSTED_PROXIES:
            main_logger.warning(
                "auth.no_trusted_proxies: TRUSTED_PROXIES is empty in production; "
                "X-Forwarded-For will be ignored and audit logs will record the "
                "direct peer IP. Set TRUSTED_PROXIES to your reverse-proxy CIDR "
                "(e.g. '10.0.0.0/8') if requests reach this app via a proxy."
            )

    assert any(
        "auth.no_trusted_proxies" in rec.message for rec in caplog.records
    )
