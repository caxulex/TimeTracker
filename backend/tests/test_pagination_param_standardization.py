"""
Tests for API pagination parameter standardization.

Verifies:
- Routers that previously used `limit` now accept `page_size`.
- The legacy `limit` alias still works (deprecation window).
- The new `le=1000` cap is enforced (page_size > 1000 returns 422).
- /api/time supports page_size up to 1000.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


AUDIT_LOGS_URL = "/api/admin/audit-logs"
IP_SECURITY_SUSPICIOUS_URL = "/api/security/ip/suspicious"
REPORT_HISTORY_URL = "/api/reports/scheduled/history"


# ---------- /api/admin/audit-logs ----------

class TestAuditLogsPagination:
    async def test_accepts_page_size(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            AUDIT_LOGS_URL,
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            AUDIT_LOGS_URL,
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            AUDIT_LOGS_URL,
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    async def test_page_size_1000_accepted(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            AUDIT_LOGS_URL,
            params={"page_size": 1000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200


# ---------- /api/pay-rates ----------

class TestPayRatesPagination:
    async def test_accepts_page_size(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/pay-rates",
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/pay-rates",
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/pay-rates",
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ---------- /api/payroll/periods ----------

class TestPayrollPeriodsPagination:
    async def test_accepts_page_size(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/payroll/periods",
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/payroll/periods",
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/payroll/periods",
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ---------- /api/security/ip/suspicious ----------

class TestIpSecurityPagination:
    async def test_accepts_page_size(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            IP_SECURITY_SUSPICIOUS_URL,
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            IP_SECURITY_SUSPICIOUS_URL,
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            IP_SECURITY_SUSPICIOUS_URL,
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ---------- /api/approvals/pending ----------

class TestApprovalsPagination:
    async def test_accepts_page_size(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/approvals/pending",
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/approvals/pending",
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/approvals/pending",
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ---------- /api/reports/scheduled/history ----------

class TestReportTemplatesHistoryPagination:
    async def test_accepts_page_size(self, client: AsyncClient, auth_token: str):
        response = await client.get(
            REPORT_HISTORY_URL,
            params={"page_size": 5},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    async def test_limit_alias_still_works(self, client: AsyncClient, auth_token: str):
        response = await client.get(
            REPORT_HISTORY_URL,
            params={"limit": 5},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, auth_token: str):
        response = await client.get(
            REPORT_HISTORY_URL,
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 422


# ---------- /api/time (export-flavored cap raise) ----------

class TestTimeEntriesPageSizeCap:
    async def test_page_size_500_accepted(self, client: AsyncClient, admin_token: str):
        """page_size=500 was previously rejected (le=100). Now must succeed."""
        response = await client.get(
            "/api/time",
            params={"page_size": 500},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # Items list should never exceed the requested page size.
        assert len(data["items"]) <= 500

    async def test_page_size_1000_accepted(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/time",
            params={"page_size": 1000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_page_size_cap_enforced(self, client: AsyncClient, admin_token: str):
        response = await client.get(
            "/api/time",
            params={"page_size": 2000},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422
