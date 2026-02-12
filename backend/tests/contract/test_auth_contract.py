# ============================================
# CONTRACT TESTS — Auth endpoints
#
# Validates POST /api/auth/login → AuthToken
# Validates GET /api/auth/me → User
#
# References:
#   frontend/src/types/index.ts: AuthToken, User
# ============================================
import pytest

from .conftest import validate_auth_token_shape, validate_user_shape


class TestLoginResponseContract:
    """POST /api/auth/login response must match AuthToken interface."""

    def test_auth_token_shape_with_valid_data(self):
        token = {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "bearer",
        }
        validate_auth_token_shape(token)

    def test_auth_token_rejects_missing_access_token(self):
        token = {"refresh_token": "eyJ...", "token_type": "bearer"}
        with pytest.raises(AssertionError, match="access_token"):
            validate_auth_token_shape(token)

    def test_auth_token_rejects_missing_refresh_token(self):
        token = {"access_token": "eyJ...", "token_type": "bearer"}
        with pytest.raises(AssertionError, match="refresh_token"):
            validate_auth_token_shape(token)

    def test_auth_token_rejects_wrong_token_type(self):
        token = {
            "access_token": "eyJ...",
            "refresh_token": "eyJ...",
            "token_type": "Basic",
        }
        with pytest.raises(AssertionError, match="bearer"):
            validate_auth_token_shape(token)

    def test_auth_token_rejects_non_string_access_token(self):
        token = {
            "access_token": 12345,
            "refresh_token": "eyJ...",
            "token_type": "bearer",
        }
        with pytest.raises(AssertionError):
            validate_auth_token_shape(token)


class TestUserMeResponseContract:
    """GET /api/auth/me response must match User interface."""

    def test_user_shape_complete(self):
        user = {
            "id": 1,
            "email": "user@test.com",
            "name": "Test User",
            "role": "member",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "phone": "+1234567890",
            "job_title": "Developer",
        }
        validate_user_shape(user)

    def test_user_shape_minimal_required(self):
        user = {
            "id": 2,
            "email": "min@test.com",
            "name": "Minimal",
            "role": "admin",
            "is_active": True,
        }
        validate_user_shape(user)

    def test_user_rejects_missing_id(self):
        user = {"email": "u@t.com", "name": "T", "role": "member", "is_active": True}
        with pytest.raises(AssertionError, match="id"):
            validate_user_shape(user)

    def test_user_rejects_missing_email(self):
        user = {"id": 1, "name": "T", "role": "member", "is_active": True}
        with pytest.raises(AssertionError, match="email"):
            validate_user_shape(user)

    def test_user_rejects_wrong_type_email(self):
        user = {"id": 1, "email": 123, "name": "T", "role": "member", "is_active": True}
        with pytest.raises(AssertionError):
            validate_user_shape(user)

    def test_user_rejects_wrong_type_is_active(self):
        user = {"id": 1, "email": "u@t.com", "name": "T", "role": "member", "is_active": "yes"}
        with pytest.raises(AssertionError):
            validate_user_shape(user)

    def test_user_with_all_optional_fields(self):
        user = {
            "id": 1,
            "email": "full@test.com",
            "name": "Full User",
            "role": "super_admin",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00Z",
            "phone": "+1234567890",
            "address": "123 Main St",
            "job_title": "Engineer",
            "department": "Engineering",
            "employment_type": "full_time",
            "start_date": "2024-01-01",
            "expected_hours_per_week": 40,
            "manager_id": 5,
        }
        validate_user_shape(user)
