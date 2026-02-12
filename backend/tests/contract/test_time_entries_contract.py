# ============================================
# CONTRACT TESTS — Time entry endpoints
#
# Validates GET /api/time → TimeEntry list/paginated
# Validates POST /api/time → single TimeEntry
# Validates GET /api/time/timer → TimerStatus
#
# References:
#   frontend/src/types/index.ts: TimeEntry, TimerStatus
# ============================================
import pytest

from .conftest import (
    validate_time_entry_shape,
    validate_timer_status_shape,
    validate_paginated_response_shape,
)


class TestTimeEntryResponseContract:
    """TimeEntry response must match frontend TimeEntry interface."""

    def test_time_entry_shape_complete(self):
        entry = {
            "id": 1,
            "user_id": 1,
            "project_id": 1,
            "task_id": 2,
            "start_time": "2025-01-15T09:00:00Z",
            "end_time": "2025-01-15T17:00:00Z",
            "description": "Worked on feature",
            "duration_seconds": 28800,
            "is_running": False,
            "is_manual": False,
            "created_at": "2025-01-15T09:00:00Z",
        }
        validate_time_entry_shape(entry)

    def test_time_entry_running_timer(self):
        """Running timer has no end_time and is_running=True."""
        entry = {
            "id": 2,
            "user_id": 1,
            "start_time": "2025-01-15T09:00:00Z",
            "end_time": None,
            "duration_seconds": 0,
            "is_running": True,
            "description": "Still working",
        }
        validate_time_entry_shape(entry)

    def test_time_entry_rejects_missing_user_id(self):
        entry = {"id": 1, "start_time": "2025-01-15T09:00:00Z", "is_running": False, "duration_seconds": 0}
        with pytest.raises(AssertionError, match="user_id"):
            validate_time_entry_shape(entry)

    def test_time_entry_rejects_missing_start_time(self):
        entry = {"id": 1, "user_id": 1, "is_running": False, "duration_seconds": 0}
        with pytest.raises(AssertionError, match="start_time"):
            validate_time_entry_shape(entry)

    def test_time_entry_rejects_missing_is_running(self):
        entry = {"id": 1, "user_id": 1, "start_time": "2025-01-15T09:00:00Z", "duration_seconds": 0}
        with pytest.raises(AssertionError, match="is_running"):
            validate_time_entry_shape(entry)

    def test_time_entry_with_pause_fields(self):
        entry = {
            "id": 1,
            "user_id": 1,
            "start_time": "2025-01-15T09:00:00Z",
            "is_running": True,
            "duration_seconds": 3600,
            "is_paused": True,
            "pause_seconds": 300,
        }
        validate_time_entry_shape(entry)


class TestTimerStatusContract:
    """GET /api/time/timer must match TimerStatus interface."""

    def test_timer_not_running(self):
        status = {"is_running": False, "current_entry": None, "elapsed_seconds": 0}
        validate_timer_status_shape(status)

    def test_timer_running_with_entry(self):
        status = {
            "is_running": True,
            "is_manual": False,
            "current_entry": {
                "id": 1,
                "user_id": 1,
                "start_time": "2025-01-15T09:00:00Z",
                "end_time": None,
                "duration_seconds": 0,
                "is_running": True,
                "description": "Working",
            },
            "elapsed_seconds": 3600,
        }
        validate_timer_status_shape(status)

    def test_timer_rejects_missing_is_running(self):
        status = {"current_entry": None}
        with pytest.raises(AssertionError, match="is_running"):
            validate_timer_status_shape(status)

    def test_timer_rejects_wrong_type_is_running(self):
        status = {"is_running": "yes"}
        with pytest.raises(AssertionError):
            validate_timer_status_shape(status)


class TestTimeEntriesPaginatedContract:
    """GET /api/time returns PaginatedResponse<TimeEntry>."""

    def test_paginated_entries(self):
        data = {
            "items": [
                {
                    "id": 1,
                    "user_id": 1,
                    "start_time": "2025-01-15T09:00:00Z",
                    "end_time": "2025-01-15T17:00:00Z",
                    "is_running": False,
                    "duration_seconds": 28800,
                },
            ],
            "total": 1,
            "page": 1,
            "size": 50,
            "pages": 1,
        }
        validate_paginated_response_shape(data, validate_time_entry_shape)
