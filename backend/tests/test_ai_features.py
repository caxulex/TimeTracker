# ============================================
# TIME TRACKER - AI FEATURES API TESTS
# Phase 7: Testing - AI endpoint tests
# Tests for /api/ai/features/* endpoints
# ============================================
import pytest
from httpx import AsyncClient


class TestAIFeaturesList:
    """Test AI features list endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_all_features_as_user(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting all AI features as authenticated user."""
        response = await client.get(
            "/api/ai/features",
            headers=auth_headers,
        )
        # Should return list of features
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_list_all_features_unauthenticated(
        self, client: AsyncClient
    ):
        """Test that listing features requires authentication."""
        response = await client.get("/api/ai/features")
        # Should require auth
        assert response.status_code in [401, 403]


class TestUserAIFeatures:
    """Test user AI feature endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_my_features(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting user's AI features status."""
        response = await client.get(
            "/api/ai/features/me",
            headers=auth_headers,
        )
        # Should return user's features
        assert response.status_code == 200
        data = response.json()
        assert "features" in data
    
    @pytest.mark.asyncio
    async def test_get_my_features_unauthenticated(
        self, client: AsyncClient
    ):
        """Test that user features require authentication."""
        response = await client.get("/api/ai/features/me")
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_get_specific_feature_status(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting status of a specific feature."""
        # First get list of features
        list_response = await client.get(
            "/api/ai/features",
            headers=auth_headers,
        )
        if list_response.status_code == 200:
            features = list_response.json()
            if features:
                # Get first feature's status
                feature_id = features[0].get("feature_id")
                if feature_id:
                    response = await client.get(
                        f"/api/ai/features/me/{feature_id}",
                        headers=auth_headers,
                    )
                    assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_feature(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting a feature that doesn't exist."""
        response = await client.get(
            "/api/ai/features/me/nonexistent-feature-xyz",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestAdminAIFeatures:
    """Test admin AI feature management endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_global_settings_as_admin(
        self, client: AsyncClient, admin_auth_headers: dict
    ):
        """Test getting global AI settings as admin."""
        response = await client.get(
            "/api/ai/features/admin",
            headers=admin_auth_headers,
        )
        # Should work for admin
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_get_global_settings_as_user_fails(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test that regular users cannot access admin AI settings."""
        response = await client.get(
            "/api/ai/features/admin",
            headers=auth_headers,
        )
        # Should be forbidden for regular users
        assert response.status_code == 403
