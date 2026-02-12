# ============================================
# CONTRACT TESTS — Task endpoints
#
# Validates GET /api/tasks → response matches Task interface
#
# References:
#   frontend/src/types/index.ts: Task, TaskStatus
# ============================================
import pytest

from .conftest import validate_task_shape, validate_paginated_response_shape


class TestTaskResponseContract:
    """Task response must match frontend Task interface."""

    def test_task_shape_todo(self):
        task = {
            "id": 1,
            "name": "Build feature",
            "description": "Implement it",
            "project_id": 1,
            "status": "TODO",
            "created_at": "2025-01-01T00:00:00Z",
        }
        validate_task_shape(task)

    def test_task_shape_in_progress(self):
        task = {"id": 2, "name": "Working", "project_id": 1, "status": "IN_PROGRESS"}
        validate_task_shape(task)

    def test_task_shape_done(self):
        task = {"id": 3, "name": "Finished", "project_id": 1, "status": "DONE"}
        validate_task_shape(task)

    def test_task_rejects_invalid_status(self):
        task = {"id": 1, "name": "Bad", "project_id": 1, "status": "CANCELLED"}
        with pytest.raises(AssertionError, match="TODO|IN_PROGRESS|DONE"):
            validate_task_shape(task)

    def test_task_rejects_missing_project_id(self):
        task = {"id": 1, "name": "No project", "status": "TODO"}
        with pytest.raises(AssertionError, match="project_id"):
            validate_task_shape(task)

    def test_task_rejects_missing_name(self):
        task = {"id": 1, "project_id": 1, "status": "TODO"}
        with pytest.raises(AssertionError, match="name"):
            validate_task_shape(task)

    def test_task_with_null_description(self):
        task = {
            "id": 1,
            "name": "T",
            "project_id": 1,
            "status": "TODO",
            "description": None,
        }
        validate_task_shape(task)


class TestTasksPaginatedContract:
    """GET /api/tasks must return PaginatedResponse<Task>."""

    def test_paginated_tasks(self):
        data = {
            "items": [
                {"id": 1, "name": "T1", "project_id": 1, "status": "TODO"},
                {"id": 2, "name": "T2", "project_id": 1, "status": "DONE"},
            ],
            "total": 2,
            "page": 1,
            "size": 20,
            "pages": 1,
        }
        validate_paginated_response_shape(data, validate_task_shape)
