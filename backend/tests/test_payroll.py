"""
Tests for Payroll Periods and Entries API endpoints
"""
import pytest
from httpx import AsyncClient
from datetime import date, timedelta
from app.models import User

pytestmark = pytest.mark.asyncio


class TestPayrollPeriodCreate:
    """Tests for creating payroll periods"""

    async def test_create_payroll_period_success(
        self, client: AsyncClient, admin_token: str
    ):
        """Test successful payroll period creation by admin"""
        start_date = date.today()
        end_date = start_date + timedelta(days=13)  # Bi-weekly

        response = await client.post(
            "/api/payroll/periods",
            json={
                "name": f"Pay Period {start_date.strftime('%Y-%m-%d')}",
                "period_type": "bi_weekly",
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["period_type"] == "bi_weekly"
        assert data["status"] == "draft"

    async def test_create_payroll_period_unauthenticated(self, client: AsyncClient):
        """Test payroll period creation without auth fails"""
        response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Test Period",
                "period_type": "weekly",
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=6)),
            },
        )
        assert response.status_code == 403

    async def test_create_payroll_period_non_admin(
        self, client: AsyncClient, auth_token: str
    ):
        """Test payroll period creation by non-admin fails"""
        response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Test Period",
                "period_type": "weekly",
                "start_date": str(date.today()),
                "end_date": str(date.today() + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 403


class TestPayrollPeriodList:
    """Tests for listing payroll periods"""

    async def test_list_payroll_periods(self, client: AsyncClient, admin_token: str):
        """Test listing payroll periods as admin"""
        response = await client.get(
            "/api/payroll/periods",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_list_payroll_periods_with_status_filter(
        self, client: AsyncClient, admin_token: str
    ):
        """Test listing payroll periods filtered by status"""
        response = await client.get(
            "/api/payroll/periods",
            params={"status": "draft"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


class TestPayrollPeriodGet:
    """Tests for getting a specific payroll period"""

    async def test_get_payroll_period(self, client: AsyncClient, admin_token: str):
        """Test getting a specific payroll period"""
        # Create a period first
        start_date = date.today() + timedelta(days=30)
        create_response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Get Test Period",
                "period_type": "weekly",
                "start_date": str(start_date),
                "end_date": str(start_date + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        period_id = create_response.json()["id"]

        # Get it
        response = await client.get(
            f"/api/payroll/periods/{period_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == period_id
        assert data["name"] == "Get Test Period"

    async def test_get_payroll_period_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Test getting non-existent payroll period returns 404"""
        response = await client.get(
            "/api/payroll/periods/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


class TestPayrollPeriodUpdate:
    """Tests for updating payroll periods"""

    async def test_update_payroll_period(self, client: AsyncClient, admin_token: str):
        """Test updating a payroll period"""
        # Create a period first
        start_date = date.today() + timedelta(days=60)
        create_response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Update Test Period",
                "period_type": "weekly",
                "start_date": str(start_date),
                "end_date": str(start_date + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        period_id = create_response.json()["id"]

        # Update it
        response = await client.put(
            f"/api/payroll/periods/{period_id}",
            json={"name": "Updated Period Name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Period Name"


class TestPayrollPeriodWorkflow:
    """Tests for payroll period workflow (process, approve, mark paid)"""

    async def test_process_payroll_period(
        self, client: AsyncClient, admin_token: str
    ):
        """Test processing a payroll period"""
        # Create a period first
        start_date = date.today() + timedelta(days=90)
        create_response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Process Test Period",
                "period_type": "weekly",
                "start_date": str(start_date),
                "end_date": str(start_date + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        period_id = create_response.json()["id"]

        # Process it
        response = await client.post(
            f"/api/payroll/periods/{period_id}/process",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"  # Back to draft after processing for review


class TestPayrollEntryCreate:
    """Tests for creating payroll entries"""

    async def test_create_payroll_entry_success(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test successful payroll entry creation by admin"""
        # Create a period first
        start_date = date.today() + timedelta(days=120)
        period_response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Entry Test Period",
                "period_type": "weekly",
                "start_date": str(start_date),
                "end_date": str(start_date + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        period_id = period_response.json()["id"]

        # Create entry
        response = await client.post(
            "/api/payroll/entries",
            json={
                "payroll_period_id": period_id,
                "user_id": test_user.id,
                "regular_hours": 40.0,
                "overtime_hours": 5.0,
                
                
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["payroll_period_id"] == period_id
        assert data["user_id"] == test_user.id
        assert float(data["regular_hours"]) == 40.0


class TestPayrollEntryUpdate:
    """Tests for updating payroll entries"""

    async def test_update_payroll_entry(
        self, client: AsyncClient, admin_token: str, test_user: User
    ):
        """Test updating a payroll entry"""
        # Create a period first
        start_date = date.today() + timedelta(days=150)
        period_response = await client.post(
            "/api/payroll/periods",
            json={
                "name": "Entry Update Test Period",
                "period_type": "weekly",
                "start_date": str(start_date),
                "end_date": str(start_date + timedelta(days=6)),
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        period_id = period_response.json()["id"]

        # Create entry
        entry_response = await client.post(
            "/api/payroll/entries",
            json={
                "payroll_period_id": period_id,
                "user_id": test_user.id,
                "regular_hours": 40.0,
                "overtime_hours": 0.0,
                "regular_rate": 20.00,
                "overtime_rate": 30.00,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        entry_id = entry_response.json()["id"]

        # Update entry
        response = await client.put(
            f"/api/payroll/entries/{entry_id}",
            json={"overtime_hours": 8.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["overtime_hours"]) == 8.0




