"""B15 — logout revokes both access and refresh tokens.

Before B15, ``POST /api/auth/logout`` only blacklisted the access
token's JTI; the refresh token survived and could be exchanged for
fresh access tokens after "logout". After B15, the client supplies the
refresh token in the request body and both JTIs are blacklisted.
A logout call without a refresh token still succeeds (200) and only
blacklists the access token, but emits a ``auth.logout_missing_refresh``
WARNING.

These tests stub Redis at the dependency level
(``token_blacklist.get_redis``) because B4 made the auth path
fail-closed when Redis is unreachable.
"""

import logging
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models import User
from app.services.auth_service import auth_service


@contextmanager
def stub_redis_and_blacklist():
    blacklisted: set[str] = set()

    async def fake_blacklist_token(jti: str, expires_in: int) -> bool:
        blacklisted.add(jti)
        return True

    async def fake_is_blacklisted(jti: str) -> bool:
        return jti in blacklisted

    async def fake_get_redis():
        redis = AsyncMock()

        async def _exists(key: str):
            # Keys are formatted as ``<prefix>:<jti>``.
            return 1 if key.split(":", 1)[1] in blacklisted else 0

        redis.exists = AsyncMock(side_effect=_exists)
        return redis

    with patch(
        "app.routers.auth.token_blacklist.blacklist_token",
        new=fake_blacklist_token,
    ), patch(
        "app.routers.auth.token_blacklist.is_blacklisted",
        new=fake_is_blacklisted,
    ), patch(
        "app.dependencies.token_blacklist.get_redis",
        new=fake_get_redis,
    ):
        yield blacklisted


class TestLogoutBlacklistsBothTokens:
    @pytest.mark.asyncio
    async def test_logout_with_both_tokens_blacklists_both(
        self, client: AsyncClient, test_user: User
    ):
        tokens = auth_service.create_tokens(test_user.id, test_user.email)
        with stub_redis_and_blacklist() as blacklist:
            response = await client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={"refresh_token": tokens["refresh_token"]},
            )

            assert response.status_code == 200
            assert tokens["access_jti"] in blacklist
            assert tokens["refresh_jti"] in blacklist

    @pytest.mark.asyncio
    async def test_logout_without_refresh_logs_warning(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
        caplog,
    ):
        """B15: logout without a refresh token still returns 200 (the
        access token is blacklisted) but emits a WARNING with the
        ``auth.logout_missing_refresh`` identifier so operators can
        detect frontends that have not been updated."""
        with stub_redis_and_blacklist():
            with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
                response = await client.post(
                    "/api/auth/logout", headers=auth_headers
                )

        assert response.status_code == 200
        assert any(
            "auth.logout_missing_refresh" in rec.getMessage()
            for rec in caplog.records
        ), [rec.getMessage() for rec in caplog.records]

    @pytest.mark.asyncio
    async def test_logout_with_invalid_refresh_logs_warning(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict,
        caplog,
    ):
        """B15: an invalid refresh token still produces 200 + WARNING.
        The access token is always blacklisted."""
        with stub_redis_and_blacklist():
            with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
                response = await client.post(
                    "/api/auth/logout",
                    headers=auth_headers,
                    json={"refresh_token": "not-a-real-jwt"},
                )

        assert response.status_code == 200
        assert any(
            "auth.logout_missing_refresh" in rec.getMessage()
            and "invalid_refresh_token" in rec.getMessage()
            for rec in caplog.records
        )

    @pytest.mark.asyncio
    async def test_refresh_after_full_logout_is_rejected(
        self, client: AsyncClient, test_user: User
    ):
        """B15 end-to-end: login → logout (with refresh) → refresh
        attempt must fail because the refresh JTI is now blacklisted."""
        tokens = auth_service.create_tokens(test_user.id, test_user.email)
        with stub_redis_and_blacklist():
            r1 = await client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                json={"refresh_token": tokens["refresh_token"]},
            )
            assert r1.status_code == 200

            r2 = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
            assert r2.status_code == 401
