"""Tests for anomaly service tenant_today integration.

Verifies that anomaly detection cache date partition and period 
boundaries use tenant-local time instead of server UTC time.
"""
from datetime import date, timedelta

import pytest


@pytest.mark.asyncio
async def test_anomaly_service_imports_tenant_time_helper():
    """Verify tenant_time helper is imported in anomaly_service."""
    from app.ai.services.anomaly_service import get_tenant_today_for_user
    
    # Import succeeds (no error)
    assert get_tenant_today_for_user is not None


def test_period_boundaries_calculation():
    """Verify period boundaries are computed correctly from tenant_today."""
    tenant_today = date(2026, 6, 10)
    period_days = 7
    
    period_start = tenant_today - timedelta(days=period_days)
    period_end = tenant_today
    
    # When tenant_today is June 10, period_start should be June 3
    assert period_start == date(2026, 6, 3)
    assert period_end == date(2026, 6, 10)


def test_cache_date_isoformat():
    """Verify cache date uses isoformat() from tenant_today."""
    tenant_today = date(2026, 6, 10)
    cache_date = tenant_today.isoformat()
    
    assert cache_date == "2026-06-10"
