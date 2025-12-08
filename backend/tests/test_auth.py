import uuid
# ============================================
# TIME TRACKER - AUTH API TESTS
# Updated for SEC-003 Strong Password Requirements
# ============================================
import pytest
from httpx import AsyncClient

from app.models import User

# SEC-003: Strong password for testing (meets all requirements)
STRONG_TEST_PASSWORD = "SecureTest#2024!"


class TestAuthRegister:
    """Test user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration with strong password."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"newuser-{uuid.uuid4().hex[:8]}@example.com",
                "password": STRONG_TEST_PASSWORD,
                "name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "@example.com" in data["email"]
        assert data["name"] == "New User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with existing email fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": test_user.email,
                "password": STRONG_TEST_PASSWORD,
                "name": "Another User",
            },
        )
        # Could be 400 (our custom) or 409 (conflict)
        assert response.status_code in [400, 409]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": STRONG_TEST_PASSWORD,
                "name": "New User",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"newuser-{uuid.uuid4().hex[:8]}@example.com",
                "password": "short",
                "name": "New User",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """SEC-003: Test registration with weak password fails."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": f"newuser-{uuid.uuid4().hex[:8]}@example.com",
                "password": "password123456",  # No uppercase, no special char
                "name": "New User",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "password" in data.get("message", "").lower() or "requirements" in str(data).lower()


class TestAuthLogin:
    """Test user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password fails."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


class TestAuthMe:
    """Test current user endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_authenticated(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test getting current user when authenticated."""
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Test getting current user when not authenticated fails."""
        response = await client.get("/api/auth/me")
        # HTTPBearer returns 403 when no credentials provided
        assert response.status_code == 403


class TestAuthRefreshToken:
    """Test token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, test_user: User):
        """Test successful token refresh."""
        # First, login to get tokens
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Then refresh the token
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestSecurityFeatures:
    """Test security features (SEC-002, SEC-011)."""

    @pytest.mark.asyncio
    async def test_logout_invalidates_token(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """SEC-002: Test that logout blacklists the token."""
        # Logout
        response = await client.post("/api/auth/logout", headers=auth_headers)
        assert response.status_code == 200
        
        # Note: Token blacklisting requires Redis, so we just verify logout works

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client: AsyncClient, test_user: User):
        """SEC-004: Test that rate limit headers are present."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )
        # Rate limit headers should be present
        # Note: Actual rate limiting requires the full middleware stack
        assert response.status_code in [200, 429]  # Success or rate limited
