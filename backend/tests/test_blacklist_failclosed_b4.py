"""B4 — JWT blacklist fails closed when Redis is unreachable.

The previous behavior swallowed Redis errors and let the request through
(fail-open). After B4, an HTTP request whose blacklist check raises must
return 401 with a stable detail string, and a WebSocket connection in the
same state must be closed with code 1011 (server error).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models import User


class TestBlacklistFailClosedHTTP:
    @pytest.mark.asyncio
    async def test_redis_outage_returns_401(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """B4: when the blacklist backend raises, the HTTP request must
        be rejected with a recognizable 401 — not silently allowed."""
        with patch(
            "app.dependencies.token_blacklist.get_redis",
            new=AsyncMock(side_effect=ConnectionError("redis down")),
        ):
            response = await client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 401
        assert (
            response.json().get("detail")
            == "Authentication service temporarily unavailable"
        )

    @pytest.mark.asyncio
    async def test_blacklisted_token_still_rejected(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """B4 regression: the constraint path (token actually blacklisted)
        must still return 401 with the existing detail string."""
        # Force redis_client.exists() to report the JTI as present.
        fake_redis = AsyncMock()
        fake_redis.exists = AsyncMock(return_value=1)
        with patch(
            "app.dependencies.token_blacklist.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ):
            response = await client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 401
        assert response.json().get("detail") == "Token has been revoked"

    @pytest.mark.asyncio
    async def test_clean_token_with_healthy_redis_passes(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """B4 regression: a non-blacklisted token + healthy Redis must
        still authenticate successfully (no false-positive failure)."""
        fake_redis = AsyncMock()
        fake_redis.exists = AsyncMock(return_value=0)
        with patch(
            "app.dependencies.token_blacklist.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ):
            response = await client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        assert response.json().get("id") == test_user.id


class TestBlacklistFailClosedWS:
    @pytest.mark.asyncio
    async def test_ws_redis_outage_closes_with_1011(self, test_user: User):
        """B4: a WebSocket connection whose blacklist check fails must be
        closed with code 1011 (server error). Tested at the dependency
        level: ``get_current_user_ws`` must raise
        ``BlacklistUnavailableError`` so the websocket router can close
        with the correct code."""
        from app.dependencies import (
            BlacklistUnavailableError,
            get_current_user_ws,
        )
        from app.services.auth_service import auth_service

        token = auth_service.create_tokens(test_user.id, test_user.email)[
            "access_token"
        ]

        with patch(
            "app.dependencies.token_blacklist.get_redis",
            new=AsyncMock(side_effect=ConnectionError("redis down")),
        ):
            with pytest.raises(BlacklistUnavailableError):
                await get_current_user_ws(token)
