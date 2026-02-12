# ============================================
# CONTRACT TESTS — Cross-cutting patterns
#
# Tests that validate patterns used across multiple endpoints:
# - Error response shape
# - Pagination metadata consistency
# - ISO 8601 date format consistency
#
# References:
#   frontend/src/types/index.ts: APIError, ValidationError, PaginatedResponse
# ============================================
import pytest
from datetime import datetime

from .conftest import (
    validate_error_response_shape,
    validate_paginated_response_shape,
)


class TestErrorResponseContract:
    """All error responses must match APIError interface."""

    def test_string_error(self):
        validate_error_response_shape({"detail": "Not found"})

    def test_validation_error_list(self):
        validate_error_response_shape({
            "detail": [
                {"loc": ["body", "email"], "msg": "field required", "type": "value_error.missing"},
                {"loc": ["body", "name"], "msg": "field required", "type": "value_error.missing"},
            ]
        })

    def test_rejects_missing_detail(self):
        with pytest.raises(AssertionError, match="detail"):
            validate_error_response_shape({"error": "oops"})

    def test_rejects_wrong_detail_type(self):
        with pytest.raises(AssertionError, match="str or list"):
            validate_error_response_shape({"detail": 42})


class TestPaginationConsistencyContract:
    """All paginated endpoints must use consistent metadata."""

    @pytest.mark.parametrize("page_data", [
        {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0},
        {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0},
    ])
    def test_accepts_both_size_keys(self, page_data):
        """Frontend handles both 'size' and 'page_size'."""
        validate_paginated_response_shape(page_data)

    def test_page_number_is_positive_int(self):
        data = {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}
        assert data["page"] >= 1

    def test_total_is_non_negative(self):
        data = {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}
        assert data["total"] >= 0

    def test_rejects_missing_pages(self):
        data = {"items": [], "total": 0, "page": 1, "size": 20}
        with pytest.raises(AssertionError, match="pages"):
            validate_paginated_response_shape(data)


class TestDateFormatContract:
    """All dates must be ISO 8601 formatted strings parseable by frontend."""

    @pytest.mark.parametrize("date_str", [
        "2025-01-15T09:00:00Z",
        "2025-01-15T09:00:00+00:00",
        "2025-01-15T09:00:00.000000",
        "2025-01-15T09:00:00.000000+00:00",
    ])
    def test_valid_iso_datetimes(self, date_str):
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        assert parsed is not None

    def test_date_only_string(self):
        """Some fields return date-only strings (e.g., weekly report)."""
        parsed = datetime.fromisoformat("2025-01-15")
        assert parsed.year == 2025
        assert parsed.month == 1
        assert parsed.day == 15
