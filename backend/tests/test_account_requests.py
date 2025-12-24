"""
Tests for Account Requests API
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models import User, AccountRequest


class TestAccountRequestSubmission:
    """Tests for public account request submission"""

    async def test_submit_valid_request(self, client: AsyncClient):
        """Test submitting a valid account request"""
        data = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+1 (555) 123-4567",
            "job_title": "Software Engineer",
            "department": "Engineering",
            "message": "I would like to join the team",
        }
        
        response = await client.post("/api/account-requests", json=data)
        
        assert response.status_code == 201
        result = response.json()
        assert result["name"] == data["name"]
        assert result["email"] == data["email"].lower()
        assert result["status"] == "pending"
        assert result["id"] is not None

    async def test_submit_minimal_request(self, client: AsyncClient):
        """Test submitting with only required fields"""
        data = {
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
        }
        
        response = await client.post("/api/account-requests", json=data)
        
        assert response.status_code == 201
        result = response.json()
        assert result["name"] == data["name"]
        assert result["phone"] is None
        assert result["job_title"] is None

    async def test_submit_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test submitting request with existing user email"""
        data = {
            "name": "Test User",
            "email": test_user.email,
        }
        
        response = await client.post("/api/account-requests", json=data)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_submit_duplicate_pending_request(self, client: AsyncClient, db_session):
        """Test submitting duplicate pending request"""
        # First request
        data = {
            "name": "Bob Wilson",
            "email": "bob.wilson@example.com",
        }
        
        response1 = await client.post("/api/account-requests", json=data)
        assert response1.status_code == 201
        
        # Second request with same email
        response2 = await client.post("/api/account-requests", json=data)
        assert response2.status_code == 400
        assert "pending" in response2.json()["detail"].lower()

    async def test_submit_invalid_email(self, client: AsyncClient):
        """Test submitting with invalid email format"""
        data = {
            "name": "Invalid Email",
            "email": "not-an-email",
        }
        
        response = await client.post("/api/account-requests", json=data)
        
        assert response.status_code == 422  # Validation error

    async def test_submit_missing_required_fields(self, client: AsyncClient):
        """Test submitting without required fields"""
        data = {
            "email": "test@example.com",
            # Missing name
        }
        
        response = await client.post("/api/account-requests", json=data)
        
        assert response.status_code == 422


class TestAccountRequestAdminEndpoints:
    """Tests for admin account request management"""

    async def test_list_requests_requires_admin(self, client: AsyncClient, auth_headers):
        """Test that listing requests requires admin role"""
        response = await client.get("/api/account-requests", headers=auth_headers)
        
        # Regular user should get 403
        assert response.status_code == 403

    async def test_list_requests_as_admin(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test listing requests as admin"""
        # Create some test requests
        request1 = AccountRequest(
            name="Alice Test",
            email="alice@example.com",
            status="pending"
        )
        request2 = AccountRequest(
            name="Bob Test",
            email="bob@example.com",
            status="approved"
        )
        db_session.add_all([request1, request2])
        await db_session.commit()
        
        response = await client.get("/api/account-requests", headers=admin_auth_headers)
        
        assert response.status_code == 200
        result = response.json()
        assert "items" in result
        assert result["total"] >= 2

    async def test_filter_by_status(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test filtering requests by status"""
        # Create requests with different statuses
        pending = AccountRequest(name="Pending", email="pending@example.com", status="pending")
        approved = AccountRequest(name="Approved", email="approved@example.com", status="approved")
        db_session.add_all([pending, approved])
        await db_session.commit()
        
        response = await client.get(
            "/api/account-requests?status=pending",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert all(item["status"] == "pending" for item in result["items"])

    async def test_search_requests(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test searching requests by name/email"""
        request = AccountRequest(
            name="Searchable Name",
            email="searchable@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        
        response = await client.get(
            "/api/account-requests?search=Searchable",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert len(result["items"]) >= 1
        assert any("Searchable" in item["name"] for item in result["items"])

    async def test_get_request_by_id(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test getting a specific request"""
        request = AccountRequest(
            name="Specific Request",
            email="specific@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.get(
            f"/api/account-requests/{request.id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == request.id
        assert result["name"] == "Specific Request"

    async def test_get_nonexistent_request(self, client: AsyncClient, admin_auth_headers):
        """Test getting a request that doesn't exist"""
        response = await client.get(
            "/api/account-requests/99999",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 404


class TestAccountRequestApproval:
    """Tests for approving account requests"""

    async def test_approve_pending_request(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test approving a pending request"""
        request = AccountRequest(
            name="To Approve",
            email="approve@example.com",
            phone="+1234567890",
            job_title="Developer",
            department="IT",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.post(
            f"/api/account-requests/{request.id}/approve",
            headers=admin_auth_headers,
            json={"admin_notes": "Looks good!"}
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Check response contains prefill data
        assert "prefill_data" in result
        assert result["prefill_data"]["name"] == "To Approve"
        assert result["prefill_data"]["email"] == "approve@example.com"
        
        # Verify database updated
        await db_session.refresh(request)
        assert request.status == "approved"
        assert request.reviewed_by is not None
        assert request.reviewed_at is not None
        assert request.admin_notes == "Looks good!"

    async def test_approve_already_processed_request(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test approving an already approved request"""
        request = AccountRequest(
            name="Already Approved",
            email="already@example.com",
            status="approved"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.post(
            f"/api/account-requests/{request.id}/approve",
            headers=admin_auth_headers,
            json={}
        )
        
        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    async def test_approve_requires_admin(self, client: AsyncClient, auth_headers, db_session):
        """Test that approval requires admin role"""
        request = AccountRequest(
            name="Need Admin",
            email="needadmin@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.post(
            f"/api/account-requests/{request.id}/approve",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 403


class TestAccountRequestRejection:
    """Tests for rejecting account requests"""

    async def test_reject_pending_request(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test rejecting a pending request"""
        request = AccountRequest(
            name="To Reject",
            email="reject@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.post(
            f"/api/account-requests/{request.id}/reject",
            headers=admin_auth_headers,
            json={"admin_notes": "Insufficient information"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "rejected"
        
        # Verify database
        await db_session.refresh(request)
        assert request.status == "rejected"
        assert request.admin_notes == "Insufficient information"

    async def test_reject_already_processed(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test rejecting an already rejected request"""
        request = AccountRequest(
            name="Already Rejected",
            email="alreadyrej@example.com",
            status="rejected"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.post(
            f"/api/account-requests/{request.id}/reject",
            headers=admin_auth_headers,
            json={}
        )
        
        assert response.status_code == 400


class TestAccountRequestDeletion:
    """Tests for deleting account requests"""

    async def test_delete_request(self, client: AsyncClient, admin_auth_headers, db_session):
        """Test deleting an account request"""
        request = AccountRequest(
            name="To Delete",
            email="delete@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        request_id = request.id
        
        response = await client.delete(
            f"/api/account-requests/{request_id}",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify deletion
        result = await db_session.execute(
            select(AccountRequest).where(AccountRequest.id == request_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_request(self, client: AsyncClient, admin_auth_headers):
        """Test deleting a request that doesn't exist"""
        response = await client.delete(
            "/api/account-requests/99999",
            headers=admin_auth_headers
        )
        
        assert response.status_code == 404

    async def test_delete_requires_admin(self, client: AsyncClient, auth_headers, db_session):
        """Test that deletion requires admin role"""
        request = AccountRequest(
            name="Protected",
            email="protected@example.com",
            status="pending"
        )
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        
        response = await client.delete(
            f"/api/account-requests/{request.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 403
