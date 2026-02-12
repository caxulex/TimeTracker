# ============================================
# CONTRACT TESTS — Project endpoints
#
# Validates GET /api/projects → PaginatedResponse<Project>
#
# References:
#   frontend/src/types/index.ts: Project, PaginatedResponse
# ============================================
import pytest

from .conftest import validate_project_shape, validate_paginated_response_shape


class TestProjectResponseContract:
    """Project response must match frontend Project interface."""

    def test_project_shape_complete(self):
        project = {
            "id": 1,
            "name": "Test Project",
            "description": "A description",
            "team_id": 1,
            "color": "#3B82F6",
            "is_archived": False,
            "created_at": "2025-01-01T00:00:00Z",
            "budget_amount": 50000.0,
            "deadline": "2025-12-31",
        }
        validate_project_shape(project)

    def test_project_shape_minimal(self):
        project = {
            "id": 2,
            "name": "Minimal",
            "team_id": 1,
            "color": "#FF0000",
            "is_archived": False,
        }
        validate_project_shape(project)

    def test_project_rejects_missing_name(self):
        project = {"id": 1, "team_id": 1, "color": "#FFF", "is_archived": False}
        with pytest.raises(AssertionError, match="name"):
            validate_project_shape(project)

    def test_project_rejects_missing_team_id(self):
        project = {"id": 1, "name": "P", "color": "#FFF", "is_archived": False}
        with pytest.raises(AssertionError, match="team_id"):
            validate_project_shape(project)

    def test_project_rejects_wrong_type_is_archived(self):
        project = {"id": 1, "name": "P", "team_id": 1, "color": "#FFF", "is_archived": "no"}
        with pytest.raises(AssertionError):
            validate_project_shape(project)

    def test_project_with_null_description(self):
        """Project description can be null per frontend interface."""
        project = {
            "id": 1,
            "name": "P",
            "team_id": 1,
            "color": "#FFF",
            "is_archived": False,
            "description": None,
        }
        validate_project_shape(project)


class TestProjectsPaginatedContract:
    """GET /api/projects must return PaginatedResponse<Project>."""

    def test_paginated_projects_shape(self):
        data = {
            "items": [
                {
                    "id": 1,
                    "name": "P1",
                    "team_id": 1,
                    "color": "#FFF",
                    "is_archived": False,
                    "created_at": "2025-01-01T00:00:00Z",
                },
            ],
            "total": 1,
            "page": 1,
            "size": 20,
            "pages": 1,
        }
        validate_paginated_response_shape(data, validate_project_shape)

    def test_paginated_empty_list(self):
        data = {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}
        validate_paginated_response_shape(data)

    def test_paginated_rejects_missing_items(self):
        data = {"total": 0, "page": 1, "size": 20, "pages": 0}
        with pytest.raises(AssertionError, match="items"):
            validate_paginated_response_shape(data)

    def test_paginated_rejects_missing_total(self):
        data = {"items": [], "page": 1, "size": 20, "pages": 0}
        with pytest.raises(AssertionError, match="total"):
            validate_paginated_response_shape(data)
