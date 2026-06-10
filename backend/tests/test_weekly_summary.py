from datetime import date

import pytest

from app.ai.services.reporting_service import AIReportingService


@pytest.mark.asyncio
async def test_same_day_of_week_comparison_mid_week():
    service = AIReportingService(db=None)

    context = service._build_week_comparison_context(
        week_start=date(2026, 6, 8),   # Mon
        week_end=date(2026, 6, 14),    # Sun
        reference_date=date(2026, 6, 10),  # Wed
    )

    assert context["comparison_end"] == date(2026, 6, 10)
    assert context["previous_week_start"] == date(2026, 6, 1)
    assert context["previous_week_end"] == date(2026, 6, 3)
    assert context["is_week_complete"] is False
    assert context["comparison_range_label"] == "Mon-Wed"
    assert context["comparison_label"] == "vs Same Period Last Week (Mon-Wed)"


@pytest.mark.asyncio
async def test_same_day_of_week_comparison_week_complete():
    service = AIReportingService(db=None)

    context = service._build_week_comparison_context(
        week_start=date(2026, 6, 8),   # Mon
        week_end=date(2026, 6, 14),    # Sun
        reference_date=date(2026, 6, 14),  # Sun
    )

    assert context["comparison_end"] == date(2026, 6, 14)
    assert context["previous_week_start"] == date(2026, 6, 1)
    assert context["previous_week_end"] == date(2026, 6, 7)
    assert context["is_week_complete"] is True
    assert context["comparison_range_label"] == "full week"
    assert context["comparison_label"] == "vs Last Week"


@pytest.mark.asyncio
async def test_insight_text_indicates_partial_week_when_in_progress():
    service = AIReportingService(db=None)

    insights = await service._generate_insights(
        metrics={
            "hours_change_pct": -58,
            "comparison_suffix": "vs same period last week (Mon-Wed)",
            "max_daily_hours": 0,
            "projects_count": 1,
        },
        week_start=date(2026, 6, 8),
        week_end=date(2026, 6, 14),
    )

    decrease_insight = next(i for i in insights if i.title == "Hours Decreased")
    assert "vs same period last week (Mon-Wed)" in decrease_insight.description


@pytest.mark.asyncio
async def test_no_duplicate_insights_between_categories():
    service = AIReportingService(db=None)

    all_insights = await service._generate_insights(
        metrics={
            "hours_change_pct": -58,
            "comparison_suffix": "vs same period last week (Mon-Wed)",
            "max_daily_hours": 0,
            "projects_count": 1,
        },
        week_start=date(2026, 6, 8),
        week_end=date(2026, 6, 14),
    )

    visible_insights = service._filter_primary_insights(all_insights)
    attention_items = service._extract_attention_items(all_insights)

    assert all(i.title != "Hours Decreased" for i in visible_insights)
    assert any(item["title"] == "Hours Decreased" for item in attention_items)
