# ============================================
# TIME TRACKER - CONTRACT TEST FIXTURES & VALIDATORS
# Validates response shapes against frontend TypeScript interfaces.
#
# Reference: frontend/src/types/index.ts
# ============================================
import pytest


# ============================================
# FIELD VALIDATORS
# ============================================

def assert_field_type(obj: dict, field: str, expected_type, nullable: bool = False):
    """Assert a field exists and has the expected type."""
    assert field in obj, (
        f"Missing required field: '{field}'. Keys present: {list(obj.keys())}"
    )
    if nullable and obj[field] is None:
        return
    assert isinstance(obj[field], expected_type), (
        f"Field '{field}' expected {expected_type}, "
        f"got {type(obj[field]).__name__} (value: {obj[field]!r})"
    )


def assert_optional_field(obj: dict, field: str, expected_type):
    """Assert a field, if present, has the expected type (or is None)."""
    if field not in obj:
        return  # optional means it can be absent
    if obj[field] is None:
        return
    assert isinstance(obj[field], expected_type), (
        f"Optional field '{field}' expected {expected_type} or None, "
        f"got {type(obj[field]).__name__}"
    )


# ============================================
# SHAPE VALIDATORS — mirror frontend/src/types/index.ts
# ============================================

def validate_user_shape(user: dict):
    """
    Validate response matches frontend User interface.
    Reference: frontend/src/types/index.ts — User
    """
    assert_field_type(user, "id", int)
    assert_field_type(user, "email", str)
    assert_field_type(user, "name", str)
    assert_field_type(user, "role", str)
    assert_field_type(user, "is_active", bool)
    assert_optional_field(user, "created_at", str)
    assert_optional_field(user, "phone", str)
    assert_optional_field(user, "job_title", str)
    assert_optional_field(user, "department", str)
    assert_optional_field(user, "employment_type", str)
    assert_optional_field(user, "start_date", str)
    assert_optional_field(user, "expected_hours_per_week", (int, float))
    assert_optional_field(user, "manager_id", int)


def validate_auth_token_shape(token: dict):
    """
    Validate response matches frontend AuthToken interface.
    Reference: frontend/src/types/index.ts — AuthToken
    """
    assert_field_type(token, "access_token", str)
    assert_field_type(token, "refresh_token", str)
    assert_field_type(token, "token_type", str)
    assert token["token_type"] == "bearer", (
        f"token_type should be 'bearer', got '{token['token_type']}'"
    )


def validate_project_shape(project: dict):
    """
    Validate response matches frontend Project interface.
    Reference: frontend/src/types/index.ts — Project
    """
    assert_field_type(project, "id", int)
    assert_field_type(project, "name", str)
    assert_field_type(project, "team_id", int)
    assert_field_type(project, "color", str)
    assert_field_type(project, "is_archived", bool)
    assert_optional_field(project, "description", str)
    assert_optional_field(project, "created_at", str)
    assert_optional_field(project, "budget_amount", (int, float))
    assert_optional_field(project, "deadline", str)


def validate_task_shape(task: dict):
    """
    Validate response matches frontend Task interface.
    Reference: frontend/src/types/index.ts — Task
    """
    assert_field_type(task, "id", int)
    assert_field_type(task, "name", str)
    assert_field_type(task, "project_id", int)
    assert_field_type(task, "status", str)
    assert task["status"] in ("TODO", "IN_PROGRESS", "DONE"), (
        f"Task status must be TODO|IN_PROGRESS|DONE, got '{task['status']}'"
    )
    assert_optional_field(task, "description", str)
    assert_optional_field(task, "created_at", str)


def validate_time_entry_shape(entry: dict):
    """
    Validate response matches frontend TimeEntry interface.
    Reference: frontend/src/types/index.ts — TimeEntry
    """
    assert_field_type(entry, "id", int)
    assert_field_type(entry, "user_id", int)
    assert_field_type(entry, "start_time", str)
    assert_field_type(entry, "is_running", bool)
    assert_field_type(entry, "duration_seconds", (int, float), nullable=True)
    assert_optional_field(entry, "project_id", int)
    assert_optional_field(entry, "task_id", int)
    assert_optional_field(entry, "end_time", str)
    assert_optional_field(entry, "description", str)
    assert_optional_field(entry, "is_manual", bool)
    assert_optional_field(entry, "is_paused", bool)
    assert_optional_field(entry, "pause_seconds", (int, float))
    assert_optional_field(entry, "created_at", str)


def validate_team_shape(team: dict):
    """
    Validate response matches frontend Team interface.
    Reference: frontend/src/types/index.ts — Team
    """
    assert_field_type(team, "id", int)
    assert_field_type(team, "name", str)
    assert_field_type(team, "owner_id", int)
    assert_field_type(team, "created_at", str)
    assert_optional_field(team, "member_count", int)


def validate_team_member_shape(member: dict):
    """
    Validate response matches frontend TeamMember interface.
    Reference: frontend/src/types/index.ts — TeamMember
    """
    assert_field_type(member, "user_id", int)
    assert_field_type(member, "team_id", int)
    assert_field_type(member, "role", str)
    assert_field_type(member, "joined_at", str)
    assert_optional_field(member, "user", dict)


def validate_timer_status_shape(status: dict):
    """
    Validate response matches frontend TimerStatus interface.
    Reference: frontend/src/types/index.ts — TimerStatus
    """
    assert_field_type(status, "is_running", bool)
    assert_optional_field(status, "is_manual", bool)
    assert_optional_field(status, "current_entry", dict)
    assert_optional_field(status, "elapsed_seconds", (int, float))
    if status.get("current_entry"):
        validate_time_entry_shape(status["current_entry"])


def validate_dashboard_stats_shape(stats: dict):
    """
    Validate response matches frontend DashboardStats interface.
    Reference: frontend/src/types/index.ts — DashboardStats
    """
    assert_field_type(stats, "today_seconds", (int, float))
    assert_field_type(stats, "week_seconds", (int, float))
    assert_field_type(stats, "month_seconds", (int, float))
    assert_field_type(stats, "active_projects", int)
    assert_optional_field(stats, "running_timer", dict)


def validate_weekly_summary_shape(summary: dict):
    """
    Validate response matches frontend WeeklySummary interface.
    Reference: frontend/src/types/index.ts — WeeklySummary
    """
    assert_field_type(summary, "week_start", str)
    assert_field_type(summary, "week_end", str)
    assert_field_type(summary, "total_seconds", (int, float))
    assert_field_type(summary, "total_hours", (int, float))
    assert_field_type(summary, "daily_breakdown", list)
    for day in summary["daily_breakdown"]:
        assert_field_type(day, "date", str)
        assert_field_type(day, "total_seconds", (int, float))
        assert_field_type(day, "entry_count", int)


def validate_paginated_response_shape(data: dict, item_validator=None):
    """
    Validate response matches frontend PaginatedResponse<T> interface.
    Reference: frontend/src/types/index.ts — PaginatedResponse
    """
    assert_field_type(data, "items", list)
    assert_field_type(data, "total", int)
    assert_field_type(data, "page", int)
    # Frontend uses 'size', backend may use 'page_size' — accept either
    has_size = "size" in data or "page_size" in data
    assert has_size, f"Missing 'size' or 'page_size'. Keys: {list(data.keys())}"
    assert_field_type(data, "pages", int)

    if item_validator and data["items"]:
        for item in data["items"]:
            item_validator(item)


def validate_error_response_shape(error: dict):
    """
    Validate error response matches frontend APIError interface.
    Reference: frontend/src/types/index.ts — APIError
    """
    assert "detail" in error, (
        f"Error response must have 'detail'. Keys: {list(error.keys())}"
    )
    detail = error["detail"]
    assert isinstance(detail, (str, list)), (
        f"'detail' must be str or list, got {type(detail).__name__}"
    )
    if isinstance(detail, list):
        for item in detail:
            assert isinstance(item, dict), "Each validation error must be a dict"
            assert_field_type(item, "msg", str)
            assert_field_type(item, "type", str)
