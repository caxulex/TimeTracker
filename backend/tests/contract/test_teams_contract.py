# ============================================
# CONTRACT TESTS — Team endpoints
#
# Validates GET /api/teams → Team list
# Validates GET /api/teams/:id → Team with members
#
# References:
#   frontend/src/types/index.ts: Team, TeamMember
# ============================================
import pytest

from .conftest import (
    validate_team_shape,
    validate_team_member_shape,
    validate_paginated_response_shape,
)


class TestTeamResponseContract:
    """Team response must match frontend Team interface."""

    def test_team_shape_complete(self):
        team = {
            "id": 1,
            "name": "Engineering",
            "owner_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "member_count": 5,
        }
        validate_team_shape(team)

    def test_team_shape_minimal(self):
        team = {"id": 1, "name": "Team A", "owner_id": 1, "created_at": "2025-01-01T00:00:00Z"}
        validate_team_shape(team)

    def test_team_rejects_missing_name(self):
        team = {"id": 1, "owner_id": 1, "created_at": "2025-01-01T00:00:00Z"}
        with pytest.raises(AssertionError, match="name"):
            validate_team_shape(team)

    def test_team_rejects_missing_owner_id(self):
        team = {"id": 1, "name": "T", "created_at": "2025-01-01T00:00:00Z"}
        with pytest.raises(AssertionError, match="owner_id"):
            validate_team_shape(team)


class TestTeamMemberContract:
    """TeamMember shape must match frontend interface."""

    def test_team_member_shape(self):
        member = {
            "user_id": 1,
            "team_id": 1,
            "role": "admin",
            "joined_at": "2025-01-01T00:00:00Z",
            "user": {
                "id": 1,
                "email": "alice@test.com",
                "name": "Alice",
                "role": "admin",
                "is_active": True,
            },
        }
        validate_team_member_shape(member)

    def test_team_member_without_user(self):
        member = {
            "user_id": 2,
            "team_id": 1,
            "role": "member",
            "joined_at": "2025-01-15T00:00:00Z",
        }
        validate_team_member_shape(member)

    def test_team_member_rejects_missing_role(self):
        member = {"user_id": 1, "team_id": 1, "joined_at": "2025-01-01T00:00:00Z"}
        with pytest.raises(AssertionError, match="role"):
            validate_team_member_shape(member)


class TestTeamsPaginatedContract:
    """GET /api/teams can return PaginatedResponse<Team>."""

    def test_paginated_teams(self):
        data = {
            "items": [
                {"id": 1, "name": "Team A", "owner_id": 1, "created_at": "2025-01-01T00:00:00Z"},
                {"id": 2, "name": "Team B", "owner_id": 2, "created_at": "2025-01-02T00:00:00Z"},
            ],
            "total": 2,
            "page": 1,
            "size": 20,
            "pages": 1,
        }
        validate_paginated_response_shape(data, validate_team_shape)
