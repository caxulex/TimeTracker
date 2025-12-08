"""
Tests for Pay Rates API endpoints
"""
import pytest
from httpx import AsyncClient
from datetime import date, timedelta
from app.models import User

pytestmark = pytest.mark.asyncio


class TestPayRateCreate:
    """Tests for creating pay rates"""

    async def test_create_pay_rate_success(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test successful pay rate creation by admin"""
        response = await client.post(
            "/api/pay-rates",
            json={
                "user_id": test_user.id,
                "rate_type": "hourly",
                "base_rate": 25.00,
                "currency": "USD",
                "overtime_multiplier": 1.5,
                "effective_from": str(date.today()),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == test_user.id
        assert data["rate_type"] == "hourly"
        assert float(data["base_rate"]) == 25.00
        assert data["is_active"] is True

    async def test_create_pay_rate_unauthenticated(self, client: AsyncClient):
        """Test pay rate creation without auth fails"""
        response = await client.post(
            "/api/pay-rates",
            json={
                "user_id": 1,
                "rate_type": "hourly",
                "base_rate": 25.00,
            },
        )
        assert response.status_code == 403

    async def test_create_pay_rate_non_admin(
        self, client: AsyncClient, auth_token: str
    ):
        """Test pay rate creation by non-admin fails"""
        response = await client.post(
            "/api/pay-rates",
            json={
                "user_id": 1,
                "rate_type": "hourly",
                "base_rate": 25.00,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 403


class TestPayRateList:
    """Tests for listing pay rates"""

    async def test_list_pay_rates(self, client: AsyncClient, admin_token: str):
        """Test listing pay rates as admin"""
        response = await client.get(
            "/api/pay-rates",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_list_pay_rates_non_admin(
        self, client: AsyncClient, auth_token: str
    ):
        """Test listing pay rates by non-admin fails"""
        response = await client.get(
            "/api/pay-rates",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 403


class TestPayRateForUser:
    """Tests for getting pay rates for a specific user"""

    async def test_get_pay_rates_for_user(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test getting pay rates for a specific user"""
        # First create a pay rate
        await client.post(
            "/api/pay-rates",
            json={
                "user_id": test_user.id,
                "rate_type": "hourly",
                "base_rate": 30.00,
                "effective_from": str(date.today()),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Then get pay rates for the user
        response = await client.get(
            f"/api/pay-rates/user/{test_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_current_pay_rate_for_user(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test getting current active pay rate for a user"""
        # Create a current pay rate
        await client.post(
            "/api/pay-rates",
            json={
                "user_id": test_user.id,
                "rate_type": "hourly",
                "base_rate": 35.00,
                "effective_from": str(date.today()),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await client.get(
            f"/api/pay-rates/user/{test_user.id}/current",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


class TestPayRateUpdate:
    """Tests for updating pay rates"""

    async def test_update_pay_rate(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test updating a pay rate"""
        # Create a pay rate first
        create_response = await client.post(
            "/api/pay-rates",
            json={
                "user_id": test_user.id,
                "rate_type": "hourly",
                "base_rate": 20.00,
                "effective_from": str(date.today()),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pay_rate_id = create_response.json()["id"]

        # Update it
        response = await client.put(
            f"/api/pay-rates/{pay_rate_id}",
            json={"base_rate": 22.50},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["base_rate"]) == 22.50


class TestPayRateDelete:
    """Tests for deleting pay rates"""

    async def test_delete_pay_rate(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test deleting (deactivating) a pay rate"""
        # Create a pay rate first
        create_response = await client.post(
            "/api/pay-rates",
            json={
                "user_id": test_user.id,
                "rate_type": "hourly",
                "base_rate": 18.00,
                "effective_from": str(date.today()),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pay_rate_id = create_response.json()["id"]

        # Delete it
        response = await client.delete(
            f"/api/pay-rates/{pay_rate_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204



