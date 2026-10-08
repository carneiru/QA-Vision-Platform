"""Report periods on the user's calendar (spec: Terms, Filters, Request body)."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.ingestion.analytics.report_period import (
    Period, PeriodError, bucket_index, bucket_starts, check_period, choose_bucket, iso, local_day,
)

UTC = ZoneInfo("UTC")
LISBON = ZoneInfo("Europe/Lisbon")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def test_a_period_runs_from_local_midnight_to_the_midnight_after_to():
    p = Period(date(2026, 9, 9), date(2026, 10, 8), LISBON)
    assert p.days == 30
    assert p.start == datetime(2026, 9, 8, 23, 0, tzinfo=timezone.utc)   # Lisbon is UTC+1 in September
    assert p.end == datetime(2026, 10, 8, 23, 0, tzinfo=timezone.utc)
    assert p.out() == {"from": "2026-09-09", "to": "2026-10-08", "days": 30,
                       "start": "2026-09-08T23:00:00Z", "end": "2026-10-08T23:00:00Z"}


def test_the_previous_period_has_the_same_length_and_ends_the_day_before():
    prev = Period(date(2026, 9, 9), date(2026, 10, 8), UTC).previous()
    assert (prev.first, prev.last, prev.days) == (date(2026, 8, 10), date(2026, 9, 8), 30)


def test_a_dst_change_inside_the_period_keeps_local_days():
    # Lisbon goes from UTC+1 to UTC at 01:00 UTC on 25 October 2026
    p = Period(date(2026, 10, 24), date(2026, 10, 26), LISBON)
    assert p.start == datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    assert p.end == datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)
    starts = bucket_starts(p, "day")
    assert starts == [date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)]
    late_on_the_25th = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)  # 23:30 local, after the change
    assert bucket_index(local_day(late_on_the_25th, LISBON), starts, "day") == 1


@pytest.mark.parametrize("first,last,message", [
    (date(2026, 10, 8), date(2026, 10, 1), "from must be on or before to"),
    (date(2026, 7, 1), date(2026, 10, 1), "at most 90"),
    (date(2026, 10, 1), date(2026, 10, 10), "to is in the future"),
    (date(2025, 9, 1), date(2025, 9, 5), "more than 400 days ago"),
])
def test_check_period_names_the_rule(first, last, message):
    with pytest.raises(PeriodError, match=message):
        check_period(first, last, UTC, NOW)


def test_tomorrow_is_allowed_for_clock_skew_and_90_days_is_the_limit():
    assert check_period(date(2026, 7, 12), date(2026, 10, 9), UTC, NOW).days == 90


def test_auto_bucket_is_day_up_to_31_days_then_week():
    assert choose_bucket("auto", 31) == "day"
    assert choose_bucket("auto", 32) == "week"
    assert choose_bucket("day", 90) == "day"
    assert choose_bucket("week", 7) == "week"


def test_weeks_start_on_monday_and_cover_the_period():
    p = Period(date(2026, 9, 9), date(2026, 10, 8), UTC)   # Wednesday to Thursday
    starts = bucket_starts(p, "week")
    assert starts[0] == date(2026, 9, 7) and starts[-1] == date(2026, 10, 5)
    assert all(s.weekday() == 0 for s in starts) and len(starts) == 5
    assert bucket_index(date(2026, 9, 9), starts, "week") == 0
    assert bucket_index(date(2026, 10, 8), starts, "week") == 4
    assert bucket_index(date(2026, 10, 12), starts, "week") is None


def test_iso_is_utc_with_z():
    assert iso(datetime(2026, 10, 8, 14, 2, 11, tzinfo=timezone.utc)) == "2026-10-08T14:02:11Z"
