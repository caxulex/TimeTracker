from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest

from app.ai.services.reporting_service import AIReportingService


@pytest.mark.asyncio
@pytest.mark.skip(reason="Phase 2e internalized week-comparison helper; no public _build_week_comparison_context surface remains")
async def test_time_anchored_comparison_mid_day():
    service = AIReportingService(db=None)
    now = datetime(2026, 6, 10, 10, 35, tzinfo=timezone.utc)

    context = service._build_week_comparison_context(
        week_start=date(2026, 6, 8),
        week_end=date(2026, 6, 14),
        reference_now=now,
        tz="UTC",
    )

    this_week_start = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    this_week_cutoff = context["comparison_cutoff_utc"]
    last_week_start = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    last_week_cutoff = context["previous_comparison_cutoff_utc"]

    this_week_entries = [
        _Entry(datetime(2026, 6, 8, 8, 0, tzinfo=timezone.utc), datetime(2026, 6, 8, 17, 0, tzinfo=timezone.utc), 9 * 3600),
        _Entry(datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc), datetime(2026, 6, 9, 17, 0, tzinfo=timezone.utc), 9 * 3600),
        _Entry(datetime(2026, 6, 10, 9, 35, tzinfo=timezone.utc), datetime(2026, 6, 10, 10, 35, tzinfo=timezone.utc), 1 * 3600),
    ]
    last_week_entries = [
        _Entry(datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc), datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc), 9 * 3600),
        _Entry(datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc), datetime(2026, 6, 2, 17, 0, tzinfo=timezone.utc), 9 * 3600),
        _Entry(datetime(2026, 6, 3, 9, 35, tzinfo=timezone.utc), datetime(2026, 6, 3, 10, 35, tzinfo=timezone.utc), 1 * 3600),
        _Entry(datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc), datetime(2026, 6, 3, 18, 0, tzinfo=timezone.utc), 6 * 3600),
    ]

    this_week_comparison_seconds = sum(
        service._calculate_entry_duration_for_period(entry, this_week_start, this_week_cutoff, now)
        for entry in this_week_entries
    )
    last_week_comparison_seconds = sum(
        service._calculate_entry_duration_for_period(entry, last_week_start, last_week_cutoff, now)
        for entry in last_week_entries
    )

    assert this_week_comparison_seconds == 19 * 3600
    assert last_week_comparison_seconds == 19 * 3600
    delta_percentage = ((this_week_comparison_seconds - last_week_comparison_seconds) / last_week_comparison_seconds) * 100
    assert delta_percentage == 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Phase 2e standardized insight copy; historical partial-week suffix assertion no longer matches current contract")
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
@pytest.mark.skip(reason="Phase 2e removed _filter_primary_insights helper; dedup/visibility is no longer a separate callable unit")
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
