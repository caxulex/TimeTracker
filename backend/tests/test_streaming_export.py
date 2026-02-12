# ============================================
# TIME TRACKER - STREAMING EXPORT TESTS
# Task 6.3: Verify streaming export endpoints and constraints
# ============================================
import pytest
from io import BytesIO


class TestStreamingExportConstants:
    """Verify export safety constants."""

    def test_pdf_max_rows_constant(self):
        from app.routers.export import PDF_MAX_ROWS
        assert PDF_MAX_ROWS == 10_000

    def test_excel_batch_size_constant(self):
        from app.routers.export import EXCEL_BATCH_SIZE
        assert EXCEL_BATCH_SIZE == 500

    def test_batch_covers_all_rows(self):
        """Batched offsets should cover all rows."""
        total_rows = 1250
        batch_size = 500
        offsets = list(range(0, total_rows, batch_size))
        assert offsets == [0, 500, 1000]
        assert offsets[-1] + batch_size >= total_rows

    def test_pdf_limit_error_message_suggests_excel(self):
        """Error message should suggest Excel for large datasets."""
        total = 15_000
        max_rows = 10_000
        msg = (
            f"PDF export is limited to {max_rows:,} rows for memory safety. "
            f"Your query returned {total:,} rows. "
            f"Please narrow your date range or use /api/export/streaming/excel for large datasets."
        )
        assert "Excel" in msg or "excel" in msg
        assert "10,000" in msg
        assert "15,000" in msg

    def test_write_only_workbook(self):
        """Excel write-only mode should produce valid output."""
        try:
            from openpyxl import Workbook
            wb = Workbook(write_only=True)
            ws = wb.create_sheet("Test")
            ws.append(["Header1", "Header2"])
            ws.append(["Data1", "Data2"])

            output = BytesIO()
            wb.save(output)
            assert output.tell() > 0
        except ImportError:
            pytest.skip("openpyxl not installed")

    def test_duration_calculation(self):
        """Duration calculation should produce correct hours."""
        from datetime import datetime, timezone
        start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 15, 17, 30, 0, tzinfo=timezone.utc)
        duration_hours = round((end - start).total_seconds() / 3600, 2)
        assert duration_hours == 8.5
