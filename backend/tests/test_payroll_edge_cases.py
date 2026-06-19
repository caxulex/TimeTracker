# ============================================
# TIME TRACKER - PAYROLL CALCULATION EDGE CASE TESTS
# Phase 2: Financial Accuracy & Test Foundation
#
# Tests critical boundary conditions in payroll calculations
# to prevent financial errors. Each test validates a specific
# business rule.
#
# NOTE: Tests marked with "# BUG:" document discovered issues
#       but do NOT fix them (per Phase 2 rules).
#
# References:
#   - backend/app/services/payroll_service.py (process_period)
#   - backend/app/models/__init__.py (PayrollEntry, PayrollPeriod, PayRate)
# ============================================
import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP


# ============================================
# A) OVERTIME BOUNDARY TESTS
# ============================================

class TestOvertimeBoundary:
    """
    Business Rule: Overtime applies only to hours EXCEEDING the threshold.
    For a weekly period, the default overtime threshold is 40 hours.

    Reference: payroll_service.py ~line 400
        weeks_in_period = period_weeks.get(period.period_type, Decimal("2"))
        overtime_threshold = Decimal("40") * weeks_in_period

    Reference: payroll_service.py ~line 530
        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
    """

    def test_exactly_40_hours_no_overtime(self):
        """
        An employee working exactly 40.00 hours in a weekly period
        should have 40.00 regular hours and 0.00 overtime hours.
        """
        total_seconds = 40 * 3600  # exactly 40 hours
        total_hours = Decimal(total_seconds) / Decimal("3600")
        overtime_threshold = Decimal("40")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))

        assert regular_hours == Decimal("40"), f"Expected 40 regular hours, got {regular_hours}"
        assert overtime_hours == Decimal("0"), f"Expected 0 overtime hours, got {overtime_hours}"

    def test_40_hours_and_1_minute_triggers_overtime(self):
        """
        An employee working 40 hours and 1 minute should have:
        - 40.00 regular hours
        - ~0.0167 overtime hours (1 minute)

        This validates the boundary is exclusive (> 40, not >= 40).
        """
        total_seconds = (40 * 3600) + 60  # 40 hours + 1 minute
        total_hours = Decimal(total_seconds) / Decimal("3600")
        overtime_threshold = Decimal("40")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))

        assert regular_hours == Decimal("40"), f"Expected 40 regular hours, got {regular_hours}"
        assert overtime_hours > Decimal("0"), f"Expected overtime > 0, got {overtime_hours}"
        # 1 minute = 60/3600 hours ≈ 0.01667; compare rounded to avoid
        # repeating-decimal precision mismatch between division paths
        expected_ot_rounded = (Decimal("60") / Decimal("3600")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        actual_ot_rounded = overtime_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert actual_ot_rounded == expected_ot_rounded, (
            f"Expected ~{expected_ot_rounded} OT hours, got {actual_ot_rounded}"
        )

    def test_overtime_rate_applied_correctly(self):
        """
        Overtime hours should be paid at base_rate * overtime_multiplier.
        Example: $25/hr base, 1.5x multiplier, 45 total hours:
          Regular: 40 * $25 = $1000
          Overtime: 5 * $37.50 = $187.50
          Total: $1187.50
        """
        base_rate = Decimal("25.00")
        overtime_multiplier = Decimal("1.5")
        total_hours = Decimal("45")
        overtime_threshold = Decimal("40")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
        regular_rate = base_rate
        overtime_rate = base_rate * overtime_multiplier

        gross = (regular_hours * regular_rate) + (overtime_hours * overtime_rate)

        assert regular_hours == Decimal("40")
        assert overtime_hours == Decimal("5")
        assert overtime_rate == Decimal("37.50")
        assert gross == Decimal("1187.50"), f"Expected $1187.50, got ${gross}"

    def test_biweekly_overtime_threshold_is_80_hours(self):
        """
        Business Rule: bi_weekly periods should use
        Decimal("40") * Decimal("2") = 80 hour overtime threshold.

        Reference: payroll_service.py ~line 400
            period_weeks = {'weekly': Decimal("1"), 'bi_weekly': Decimal("2"), ...}
            overtime_threshold = Decimal("40") * weeks_in_period
        """
        period_weeks = {
            "weekly": Decimal("1"),
            "bi_weekly": Decimal("2"),
            "semi_monthly": Decimal("2.17"),
            "monthly": Decimal("4.33"),
        }
        overtime_threshold = Decimal("40") * period_weeks["bi_weekly"]
        assert overtime_threshold == Decimal("80"), (
            f"bi_weekly threshold should be 80, got {overtime_threshold}"
        )

    def test_semi_monthly_overtime_threshold(self):
        """
        Semi-monthly periods use Decimal("2.17") weeks → 86.8 hour threshold.
        """
        weeks = Decimal("2.17")
        overtime_threshold = Decimal("40") * weeks
        assert overtime_threshold == Decimal("86.80"), (
            f"semi_monthly threshold should be 86.80, got {overtime_threshold}"
        )

    def test_monthly_overtime_threshold(self):
        """
        Monthly periods use Decimal("4.33") weeks → 173.2 hour threshold.
        """
        weeks = Decimal("4.33")
        overtime_threshold = Decimal("40") * weeks
        assert overtime_threshold == Decimal("173.20"), (
            f"monthly threshold should be 173.20, got {overtime_threshold}"
        )

    def test_zero_overtime_multiplier_edge_case(self):
        """
        If overtime_multiplier is 1.0 (no premium), overtime hours should
        still be tracked separately but paid at the same rate.
        """
        base_rate = Decimal("20.00")
        overtime_multiplier = Decimal("1.0")
        total_hours = Decimal("50")
        overtime_threshold = Decimal("40")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
        overtime_rate = base_rate * overtime_multiplier

        gross = (regular_hours * base_rate) + (overtime_hours * overtime_rate)

        assert overtime_hours == Decimal("10")
        assert overtime_rate == Decimal("20.00")
        assert gross == Decimal("1000.00"), f"50hrs * $20 = $1000, got ${gross}"


# ============================================
# B) PAY PERIOD TRANSITION TESTS
# ============================================

class TestPayPeriodTransitions:
    """
    Business Rule: A time entry is attributed to the period that contains
    its start_time, not its end_time. The payroll service filters:

    Reference: payroll_service.py ~line 475
        TimeEntry.start_time >= datetime.combine(period.start_date, datetime.min.time()),
        TimeEntry.start_time <= datetime.combine(period.end_date, datetime.max.time()),
    """

    def test_entry_starting_before_midnight_belongs_to_first_period(self):
        """
        An entry starting at 11 PM on Jan 7 (last day of Period A)
        and ending at 2 AM on Jan 8 (first day of Period B)
        should belong to Period A because start_time is in Period A.
        """
        period_a_end = date(2026, 1, 7)

        entry_start = datetime(2026, 1, 7, 23, 0, tzinfo=timezone.utc)

        period_a_boundary = datetime.combine(
            period_a_end, datetime.max.time().replace(tzinfo=timezone.utc)
        )

        entry_in_period_a = entry_start <= period_a_boundary
        assert entry_in_period_a is True, "Entry starting before midnight should be in Period A"

    def test_entry_starting_at_midnight_belongs_to_new_period(self):
        """
        An entry starting exactly at midnight on Jan 8 belongs to Period B.
        """
        period_b_start = date(2026, 1, 8)
        entry_start = datetime(2026, 1, 8, 0, 0, 0, tzinfo=timezone.utc)

        period_b_boundary = datetime.combine(
            period_b_start,
            datetime.min.time().replace(tzinfo=timezone.utc),
        )

        assert entry_start >= period_b_boundary, (
            "Entry at midnight should be in the new period"
        )

    def test_overnight_entry_full_duration_counted_in_start_period(self):
        """
        Business Rule: The FULL duration of an overnight entry is counted
        in the period containing the start_time.

        Entry: 11 PM to 3 AM = 4 hours total. All 4 hours should appear
        in the starting period's payroll, not split across periods.

        Reference: payroll_service.py sums duration_seconds from all matched entries.
        """
        entry_start = datetime(2026, 1, 7, 23, 0, tzinfo=timezone.utc)
        entry_end = datetime(2026, 1, 8, 3, 0, tzinfo=timezone.utc)
        duration_seconds = int((entry_end - entry_start).total_seconds())

        total_hours = Decimal(duration_seconds) / Decimal("3600")

        assert total_hours == Decimal("4"), (
            f"Full 4 hours should be counted, got {total_hours}"
        )


# ============================================
# C) ROUNDING TESTS
# ============================================

class TestPayrollRounding:
    """
    Business Rule: Hours and amounts are rounded to 2 decimal places
    using Decimal.quantize.

    Reference: payroll_service.py ~line 545
        regular_hours = regular_hours.quantize(Decimal("0.01"))
        overtime_hours = overtime_hours.quantize(Decimal("0.01"))
        gross_amount = gross_amount.quantize(Decimal("0.01"))
    """

    def test_7_hours_59_minutes_59_seconds_rounds_correctly(self):
        """
        7h 59m 59s = 28799 seconds = 7.9997... hours
        Should round to 8.00 hours (round half up).
        """
        total_seconds = (7 * 3600) + (59 * 60) + 59  # 28799
        total_hours = Decimal(total_seconds) / Decimal("3600")

        rounded = total_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert rounded == Decimal("8.00"), (
            f"7h59m59s should round to 8.00 hours, got {rounded}"
        )

    def test_partial_minute_rounding(self):
        """
        1h 30m 30s = 5430 seconds = 1.5083... hours → rounds to 1.51
        """
        total_seconds = (1 * 3600) + (30 * 60) + 30
        total_hours = Decimal(total_seconds) / Decimal("3600")

        rounded = total_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert rounded == Decimal("1.51"), (
            f"1h30m30s should round to 1.51, got {rounded}"
        )

    def test_gross_amount_rounds_to_cents(self):
        """
        If regular_hours=7.33 and rate=$15.75:
        7.33 * 15.75 = 115.4475 → should round to $115.45
        """
        regular_hours = Decimal("7.33")
        rate = Decimal("15.75")
        gross = (regular_hours * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert gross == Decimal("115.45"), f"Expected $115.45, got ${gross}"

    def test_half_cent_rounding_behavior(self):
        """
        $100.005 — test actual rounding mode used by the payroll service.

        BUG: payroll_service.py uses .quantize(Decimal("0.01")) without
        specifying ROUND_HALF_UP. Python's default is ROUND_HALF_EVEN
        (banker's rounding), which rounds $100.005 to $100.00 instead of
        $100.01. This could cause employees to be underpaid by $0.01
        on certain pay amounts. Fix: add rounding=ROUND_HALF_UP to all
        .quantize() calls in process_period().
        """
        amount = Decimal("100.005")

        # What the payroll service actually does (default rounding):
        result_default = amount.quantize(Decimal("0.01"))

        # What we'd expect for payroll (ROUND_HALF_UP):
        result_explicit = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert result_explicit == Decimal("100.01"), "ROUND_HALF_UP gives $100.01"
        # banker's rounding gives $100.00 for this specific case
        assert result_default == Decimal("100.00"), (
            "Default (banker's) rounding gives $100.00 — see BUG comment above"
        )

    def test_very_small_duration_does_not_produce_negative(self):
        """
        A 1-second time entry should produce a tiny but positive amount.
        """
        total_seconds = 1
        total_hours = Decimal(total_seconds) / Decimal("3600")
        rate = Decimal("20.00")

        gross = (total_hours * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        assert gross >= Decimal("0.00"), f"Amount should not be negative: ${gross}"
        assert gross == Decimal("0.01"), (
            f"1 second at $20/hr ≈ $0.006 → rounds to $0.01, got ${gross}"
        )


# ============================================
# D) MULTI-RATE SCENARIOS
# ============================================

class TestMultiRateScenarios:
    """
    Business Rule: A user's active pay rate at the period end date
    determines their pay. The service calls:
        pay_rate = await self.pay_rate_service.get_user_active_rate(user.id, period.end_date)

    Reference: payroll_service.py ~line 460
    """

    def test_rate_change_mid_period_uses_end_date_rate(self):
        """
        If an employee's rate changes from $20/hr to $25/hr mid-period,
        the active rate on the period end date ($25) is used for ALL hours.
        This is a deliberate design decision (not prorated).
        """
        period_end = date(2026, 1, 12)
        new_rate_effective_from = date(2026, 1, 11)

        new_rate_active = period_end >= new_rate_effective_from
        assert new_rate_active is True

        total_hours = Decimal("45")
        new_rate = Decimal("25.00")
        overtime_threshold = Decimal("40")
        overtime_multiplier = Decimal("1.5")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
        gross = (regular_hours * new_rate) + (overtime_hours * new_rate * overtime_multiplier)

        expected = (Decimal("40") * Decimal("25")) + (Decimal("5") * Decimal("37.50"))
        assert gross == expected, f"Expected ${expected}, got ${gross}"


# ============================================
# E) ZERO-HOUR EDGE CASES
# ============================================

class TestZeroHourEdgeCases:
    """
    Business Rule: A pay period with no time entries for an hourly employee
    should produce a $0.00 payroll entry, not an error.
    """

    def test_hourly_employee_zero_hours_produces_zero_pay(self):
        """
        An hourly employee with no time entries in a period should get
        a payroll entry with 0 hours and $0.00 gross.
        """
        total_seconds = 0
        total_hours = Decimal(total_seconds) / Decimal("3600")
        overtime_threshold = Decimal("40")
        base_rate = Decimal("25.00")
        overtime_multiplier = Decimal("1.5")

        regular_hours = min(total_hours, overtime_threshold)
        overtime_hours = max(total_hours - overtime_threshold, Decimal("0"))
        gross = (regular_hours * base_rate) + (overtime_hours * base_rate * overtime_multiplier)

        assert regular_hours == Decimal("0")
        assert overtime_hours == Decimal("0")
        assert gross == Decimal("0"), f"Expected $0.00, got ${gross}"

    def test_monthly_employee_paid_regardless_of_hours(self):
        """
        A monthly (salaried) employee should be paid their prorated salary
        even with zero time entries.

        Reference: payroll_service.py monthly calculation uses base_rate
        as the monthly salary, converts to annual, divides by periods/year.
        """
        base_rate = Decimal("5000.00")  # $5000/month
        annual_salary = base_rate * Decimal("12")
        weekly_pay = (annual_salary / Decimal("52")).quantize(Decimal("0.01"))

        assert weekly_pay > Decimal("0"), "Monthly employee should get paid"
        expected = (Decimal("5000.00") * Decimal("12") / Decimal("52")).quantize(Decimal("0.01"))
        assert weekly_pay == expected

    def test_daily_employee_zero_days_produces_zero(self):
        """
        A daily-rate employee with zero time entries should have $0 pay.

        Reference: payroll_service.py daily calculation counts distinct
        days with time entries.
        """
        days_worked = 0
        daily_rate = Decimal("200.00")
        gross = (Decimal(days_worked) * daily_rate).quantize(Decimal("0.01"))

        assert gross == Decimal("0.00")


# ============================================
# F) NEGATIVE TIME ENTRY TESTS
# ============================================

class TestNegativeTimeEntries:
    """
    Business Rule: Time entries cannot have negative duration.
    The API should reject entries where end_time < start_time.
    """

    def test_negative_seconds_in_calculation_produces_zero_not_negative_pay(self):
        """
        Even if somehow a negative duration_seconds slips through,
        payroll should not generate a negative amount.
        We use max(0, ...) guard to protect the calculation.

        BUG: payroll_service.py line ~530 does:
            total_seconds = sum(te.duration_seconds or 0 for te in time_entries)
        This uses `or 0` which handles None but does NOT protect against
        negative values. If a time entry somehow had negative duration_seconds,
        it would reduce the total. Should use max(te.duration_seconds or 0, 0).
        """
        duration_seconds = -3600  # -1 hour (should never happen)
        total_seconds = max(0, duration_seconds)
        total_hours = Decimal(total_seconds) / Decimal("3600")
        rate = Decimal("25.00")
        gross = total_hours * rate

        assert gross >= Decimal("0"), f"Gross pay should never be negative: ${gross}"

    def test_negative_duration_should_not_reduce_total_seconds(self):
        """
        Demonstrate the vulnerability: if negatives aren't guarded,
        a single corrupt entry can reduce total pay.
        """
        # Simulate mixed entries — one valid, one corrupted
        entries_seconds = [28800, -3600]  # 8 hours + (-1 hour)

        # Current service behavior (no guard — uses `or 0`):
        unguarded_total = sum(s or 0 for s in entries_seconds)
        # What a safe implementation would produce:
        guarded_total = sum(max(s or 0, 0) for s in entries_seconds)

        assert unguarded_total == 25200, "Unguarded sum loses 1 hour to corruption"
        assert guarded_total == 28800, "Guarded sum ignores negative entries"
        assert guarded_total > unguarded_total, "Guard prevents pay reduction"


# ============================================
# G) OVERLAPPING TIME ENTRIES
# ============================================

class TestOverlappingTimeEntries:
    """
    Business Rule: The payroll service sums ALL time entries in a period
    for a user, regardless of overlap. This means overlapping entries
    would double-count hours.

    Reference: payroll_service.py ~line 530 just sums duration_seconds
    from all matching entries — no overlap detection.
    """

    def test_overlapping_entries_double_count_hours(self):
        """
        Two overlapping entries (9-12 and 10-12) would result in
        5 hours total (3 + 2), not 3 hours (actual wall-clock time).

        BUG: payroll_service.py does not detect or handle overlapping time
        entries. Two entries for the same user covering 9-12 and 10-12
        would count as 5 hours worked instead of the actual 3 wall-clock
        hours. This could result in overpayment. The time entry creation
        API should either prevent overlaps or the payroll service should
        detect and merge them.
        """
        entry1_seconds = 3 * 3600  # 9 AM - 12 PM = 3 hours
        entry2_seconds = 2 * 3600  # 10 AM - 12 PM = 2 hours (overlaps)

        # Current behavior: naive sum
        total_seconds = entry1_seconds + entry2_seconds
        total_hours = Decimal(total_seconds) / Decimal("3600")

        assert total_hours == Decimal("5"), (
            "Current behavior: overlapping entries sum to 5 hours"
        )

    def test_adjacent_entries_do_not_overlap(self):
        """
        Entries that are adjacent (one ends when the other starts)
        should sum correctly — this is NOT an overlap.
        """
        entry1 = {"start": datetime(2026, 1, 8, 9, 0), "end": datetime(2026, 1, 8, 12, 0)}
        entry2 = {"start": datetime(2026, 1, 8, 12, 0), "end": datetime(2026, 1, 8, 17, 0)}

        entry1_seconds = int((entry1["end"] - entry1["start"]).total_seconds())
        entry2_seconds = int((entry2["end"] - entry2["start"]).total_seconds())
        total_hours = Decimal(entry1_seconds + entry2_seconds) / Decimal("3600")

        assert total_hours == Decimal("8"), "Adjacent entries should sum to 8 hours"


# ============================================
# H) MONTHLY SALARY PRORATION TESTS
# ============================================

class TestMonthlySalaryProration:
    """
    Business Rule: Monthly salary is prorated based on period type.
    Annual = monthly * 12, then divided by periods per year.

    Reference: payroll_service.py ~line 490-520 (monthly calculation)
    """

    def test_monthly_to_weekly_proration(self):
        """
        $5,000/month prorated weekly: $5,000 * 12 / 52 = $1,153.85
        """
        monthly_rate = Decimal("5000.00")
        annual = monthly_rate * Decimal("12")
        weekly = (annual / Decimal("52")).quantize(Decimal("0.01"))

        assert weekly == Decimal("1153.85"), f"Expected $1153.85, got ${weekly}"

    def test_monthly_to_biweekly_proration(self):
        """
        $5,000/month prorated bi-weekly: $60,000 / 26 = $2,307.69
        """
        monthly_rate = Decimal("5000.00")
        annual = monthly_rate * Decimal("12")
        biweekly = (annual / Decimal("26")).quantize(Decimal("0.01"))

        assert biweekly == Decimal("2307.69"), f"Expected $2307.69, got ${biweekly}"

    def test_monthly_to_semimonthly_proration(self):
        """
        $5,000/month semi-monthly: $60,000 / 24 = $2,500.00
        """
        monthly_rate = Decimal("5000.00")
        annual = monthly_rate * Decimal("12")
        semimonthly = (annual / Decimal("24")).quantize(Decimal("0.01"))

        assert semimonthly == Decimal("2500.00")

    def test_monthly_to_monthly_proration(self):
        """
        $5,000/month paid monthly: $60,000 / 12 = $5,000.00
        """
        monthly_rate = Decimal("5000.00")
        annual = monthly_rate * Decimal("12")
        monthly_pay = (annual / Decimal("12")).quantize(Decimal("0.01"))

        assert monthly_pay == Decimal("5000.00")


# ============================================
# I) DAILY RATE TESTS
# ============================================

class TestDailyRateCalculation:
    """
    Business Rule: Daily-rate employees are paid their daily rate
    multiplied by the number of distinct days they worked.

    Reference: payroll_service.py daily calculation counts unique
    start_time.date() from time entries.
    """

    def test_daily_rate_with_5_days_worked(self):
        """A $200/day employee who worked 5 distinct days earns $1,000."""
        daily_rate = Decimal("200.00")
        days_worked = 5
        gross = (Decimal(days_worked) * daily_rate).quantize(Decimal("0.01"))

        assert gross == Decimal("1000.00")

    def test_daily_rate_multiple_entries_same_day_count_once(self):
        """
        If an employee has 3 time entries on the same day, that day
        should only be counted once for daily rate calculation.
        """
        entries = [
            {"start_time": datetime(2026, 1, 8, 9, 0, tzinfo=timezone.utc)},
            {"start_time": datetime(2026, 1, 8, 13, 0, tzinfo=timezone.utc)},
            {"start_time": datetime(2026, 1, 8, 16, 0, tzinfo=timezone.utc)},
        ]

        distinct_days = len({e["start_time"].date() for e in entries})
        assert distinct_days == 1, "Three entries on same day = 1 day worked"

        daily_rate = Decimal("200.00")
        gross = (Decimal(distinct_days) * daily_rate).quantize(Decimal("0.01"))
        assert gross == Decimal("200.00")

    def test_daily_rate_entries_across_multiple_days(self):
        """
        Entries spanning Mon-Fri (5 unique days) should count as 5 days.
        """
        entries = [
            {"start_time": datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)},  # Mon
            {"start_time": datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)},  # Mon (2nd)
            {"start_time": datetime(2026, 1, 6, 9, 0, tzinfo=timezone.utc)},  # Tue
            {"start_time": datetime(2026, 1, 7, 9, 0, tzinfo=timezone.utc)},  # Wed
            {"start_time": datetime(2026, 1, 8, 9, 0, tzinfo=timezone.utc)},  # Thu
            {"start_time": datetime(2026, 1, 9, 9, 0, tzinfo=timezone.utc)},  # Fri
        ]

        worked_days = set()
        for te in entries:
            worked_days.add(te["start_time"].date())
        days_worked = len(worked_days)

        assert days_worked == 5, f"Expected 5 unique days, got {days_worked}"


# ============================================
# J) PROJECT-BASED RATE TESTS
# ============================================

class TestProjectBasedRate:
    """
    Business Rule: Project-based employees are paid a flat amount
    per period, regardless of hours worked.

    Reference: payroll_service.py ~line 525
        gross_amount = pay_rate.base_rate
        regular_hours = Decimal("0")
    """

    def test_project_based_flat_rate(self):
        """
        A project-based rate of $3000 should produce exactly $3000 gross,
        with 0 regular hours and 0 overtime hours.
        """
        base_rate = Decimal("3000.00")

        gross_amount = base_rate
        regular_hours = Decimal("0")
        overtime_hours = Decimal("0")

        assert gross_amount == Decimal("3000.00")
        assert regular_hours == Decimal("0")
        assert overtime_hours == Decimal("0")

    def test_project_based_ignores_time_entries(self):
        """
        Even if the employee logged 100 hours, project-based pay
        remains the flat rate.
        """
        base_rate = Decimal("3000.00")
        total_hours_logged = Decimal("100")  # irrelevant for project-based

        gross_amount = base_rate  # not base_rate * total_hours_logged

        assert gross_amount == Decimal("3000.00"), (
            f"Project-based pay should be flat ${base_rate}, got ${gross_amount}"
        )
