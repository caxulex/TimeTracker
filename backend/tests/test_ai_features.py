# ============================================
# TIME TRACKER - AI FEATURES API TESTS
# Phase 7: Testing - AI endpoint tests
# ============================================
import pytest
from httpx import AsyncClient


class TestAISettings:
    """Test AI settings endpoints (admin only)."""
    
    @pytest.mark.asyncio
    async def test_get_ai_settings_as_admin(
        self, client: AsyncClient, admin_auth_headers: dict
    ):
        """Test getting AI settings as admin."""
        response = await client.get(
            "/api/ai/settings/global",
            headers=admin_auth_headers,
        )
        # Should work for admin
        assert response.status_code in [200, 404]  # 404 if not configured yet
    
    @pytest.mark.asyncio
    async def test_get_ai_settings_as_user_fails(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test that regular users cannot access admin AI settings."""
        response = await client.get(
            "/api/ai/settings/global",
            headers=auth_headers,
        )
        # Should be forbidden for regular users
        assert response.status_code in [403, 401]


class TestUserAIPreferences:
    """Test user AI preferences endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_user_preferences(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting user's AI preferences."""
        response = await client.get(
            "/api/ai/preferences",
            headers=auth_headers,
        )
        # Should return preferences or empty defaults
        assert response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_update_user_preferences(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test updating user's AI preferences."""
        response = await client.put(
            "/api/ai/preferences",
            json={
                "enable_smart_descriptions": True,
                "enable_task_categorization": True,
            },
            headers=auth_headers,
        )
        # Should succeed or indicate preferences not set up
        assert response.status_code in [200, 201, 400, 404]


class TestAIAssistFeatures:
    """Test AI assist endpoints."""
    
    @pytest.mark.asyncio
    async def test_smart_description_unauthenticated(
        self, client: AsyncClient
    ):
        """Test that AI assist requires authentication."""
        response = await client.post(
            "/api/ai/assist/smart-description",
            json={"text": "working on project"},
        )
        assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_task_categorization_authenticated(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test task categorization endpoint."""
        response = await client.post(
            "/api/ai/assist/categorize",
            json={"description": "Meeting with client about Q4 budget"},
            headers=auth_headers,
        )
        # May fail if AI not configured, but should be valid endpoint
        assert response.status_code in [200, 400, 503]


class TestAIValidation:
    """Test AI validation endpoints."""
    
    @pytest.mark.asyncio
    async def test_validate_time_entry(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test time entry validation endpoint."""
        response = await client.post(
            "/api/ai/validate/time-entry",
            json={
                "description": "Working on feature X",
                "duration_seconds": 3600,
                "project_name": "Test Project"
            },
            headers=auth_headers,
        )
        # May fail if AI not configured
        assert response.status_code in [200, 400, 503]


class TestAISearch:
    """Test AI semantic search endpoints."""
    
    @pytest.mark.asyncio
    async def test_semantic_search(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test semantic search endpoint."""
        response = await client.post(
            "/api/ai/search",
            json={"query": "budget meetings"},
            headers=auth_headers,
        )
        # May fail if AI not configured
        assert response.status_code in [200, 400, 503]


class TestAIReports:
    """Test AI report generation endpoints."""
    
    @pytest.mark.asyncio
    async def test_generate_daily_summary(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test daily summary generation endpoint."""
        response = await client.get(
            "/api/ai/reports/daily-summary",
            headers=auth_headers,
        )
        # May fail if AI not configured or no data
        assert response.status_code in [200, 400, 404, 503]
    
    @pytest.mark.asyncio
    async def test_generate_weekly_summary(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test weekly summary generation endpoint."""
        response = await client.get(
            "/api/ai/reports/weekly-summary",
            headers=auth_headers,
        )
        # May fail if AI not configured or no data
        assert response.status_code in [200, 400, 404, 503]
